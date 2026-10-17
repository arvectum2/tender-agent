"""Read-only official getDocsIP bid/application security for two pinned notices.

Never uses secondary aggregator amounts as source proof, never stores original
ZIP/XML or signed original download URLs, never changes operator/ETP state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

_SOURCES = {
    "0161600001326000063": {
        "notice_type": "epNotificationEF2020",
        "archived_revision": 1,
        "archive_sha256": "cb5ce3f2bd07bf4e6210e6d960c663730b8097dc40cf831af0ca77efd0452a2c",
        "xml_sha256": "f40f20f3add1994e6d930b9b663f370d5af758ece680deadc4047810a8d1c87c",
        "source_nmck_rub": Decimal("1600000.00"),
    },
    "0816500000626015655": {
        "notice_type": "epNotificationEOK2020",
        "archived_revision": 1,
        "archive_sha256": "1a9b334270ef80be0b2e7251aaa710c9aba40e82d0641ae134dc2059b85f1750",
        "xml_sha256": "661abad2253c297b6a9055dbcb2d84402c23eb4e9c1c15c8dff2878d1654f6bb",
        "source_nmck_rub": Decimal("4550000.00"),
    },
}


def _name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1]


def _single_child(parent: ET.Element, name: str) -> ET.Element:
    children = [e for e in parent if _name(e) == name]
    if len(children) != 1:
        raise ValueError(f"official notice missing or ambiguous: {name}")
    return children[0]


def original_application_security(xml: bytes, *, number: str, notice_type: str) -> dict:
    """Require the one right original notice parent path; not arbitrary amount."""
    if not re.fullmatch(r"\d{19}", number) or len(xml) > 2_000_000:
        raise ValueError("unsupported notice ID or XML size")
    root = ET.fromstring(xml)
    if _name(root) != "export":
        raise ValueError("not a first-party notice export")
    notice = _single_child(root, notice_type)
    common = _single_child(notice, "commonInfo")
    if (_single_child(common, "purchaseNumber").text or "").strip() != number:
        raise ValueError("registry number mismatch")
    customers = _single_child(notice, "notificationInfo")
    req = _single_child(customers, "customerRequirementsInfo")
    row = _single_child(req, "customerRequirementInfo")
    security = _single_child(row, "applicationGuarantee")
    try:
        amount = Decimal((_single_child(security, "amount").text or "").strip())
        percent = Decimal((_single_child(security, "part").text or "").strip())
    except InvalidOperation as exc:
        raise ValueError("invalid original application guarantee amount/part") from exc
    if not amount.is_finite() or amount <= 0 or not percent.is_finite() or percent <= 0:
        raise ValueError(
            "original application security requires positive finite money and percentage"
        )
    return {
        "source_xml_exact_path": (
            f"export/{notice_type}/notificationInfo/customerRequirementsInfo/"
            "customerRequirementInfo/applicationGuarantee/{amount,part}"
        ),
        "application_security_amount_rub": str(amount.quantize(Decimal("0.01"))),
        "application_security_part_percent": str(percent.quantize(Decimal("0.01"))),
        "source_reg_number": number,
    }


def collect() -> dict:
    settings = replace(get_zakupki_soap_settings(), timeout_seconds=12)
    if not (
        settings.configured
        and settings.disable_proxy_for_eis
        and settings.require_direct_ru_route
    ):
        raise ValueError("authorized direct EIS route is unavailable")
    client = ZakupkiSoapClient(settings, runtime_status_enabled=False)
    originals = []
    for number, expected in _SOURCES.items():
        response = client.get_docs_by_reestr_number(number)
        urls = response.archive_urls or (
            [response.archive_url] if response.archive_url else []
        )
        if response.status != "completed" or len(urls) != 1:
            raise ValueError("official getDocsIP ambiguous/unavailable")
        parsed = urlsplit(urls[0])
        if parsed.scheme != "https" or parsed.hostname != "int.zakupki.gov.ru":
            raise ValueError("official archival URL hostname rejected")
        with tempfile.TemporaryDirectory(prefix="ta-readonly-app-bond-") as folder:
            out = client.download_archive(urls[0], Path(folder))
            zip_path = Path(folder) / out.stored_name
            classification = classify_official_eis_archive(zip_path, number)
            if (
                classification["status"] != "ATTESTED_COMPETITIVE"
                or classification["source_version"] != expected["archived_revision"]
                or classification["notice_type"] != expected["notice_type"]
                or classification["archive_sha256"] != expected["archive_sha256"]
                or classification["notice_xml_sha256"] != expected["xml_sha256"]
            ):
                raise ValueError(
                    "original selected notice SHA/type/version changed; no stale security assertions"
                )
            name_pattern = re.compile(
                rf"{expected['notice_type']}_{number}_{expected['archived_revision']}_"
                r"[0-9A-Fa-f]{32}\.xml"
            )
            with zipfile.ZipFile(zip_path) as archive:
                selected = [
                    info.filename
                    for info in archive.infolist()
                    if name_pattern.fullmatch(info.filename)
                ]
                if len(selected) != 1:
                    raise ValueError("ambiguous original notice binary")
                original = archive.read(selected[0])
            if (
                hashlib.sha256(original).hexdigest()
                != classification["notice_xml_sha256"]
            ):
                raise ValueError("original raw XML SHA differs")
        result = original_application_security(
            original, number=number, notice_type=expected["notice_type"]
        )
        amount = Decimal(result["application_security_amount_rub"])
        ratio = Decimal(result["application_security_part_percent"])
        if amount != expected["source_nmck_rub"] * ratio / Decimal(100):
            raise ValueError("original % guarantee does not equal original NMCK amount")
        originals.append(
            {
                **result,
                "source_kind": "ORIGINAL_EIS_GETDOCSIP_ARCHIVED_XML",
                "source_archived_revision": expected["archived_revision"],
                "source_archive_sha256": classification["archive_sha256"],
                "source_original_notice_sha256": classification["notice_xml_sha256"],
                "source_original_nmck_rub": str(expected["source_nmck_rub"]),
                "checked_at_utc": datetime.now(UTC).isoformat(),
                "current_legal_bidding_status_verified": False,
                "eligible_to_bid": False,
                "cash_security_is_not_economic_expense": True,
                "guarantee_or_cash_method_is_owner_decision": True,
            }
        )
    return {
        "schema_version": "b2b-original-44fz-two-application-guarantees-v1",
        "as_of": "2026-10-17",
        "reviewed_original_procurements": 2,
        "public_44fz_application_securities": originals,
        "all_official_sources_historical_archive_only": True,
        "no_etp_action_or_payment": True,
        "company_bid_ready": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.name != "b2b_44fz_two_original_bid_securities_2026-10-17.json":
        parser.error("write only dated verified original public source receipt")
    source = collect()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for item in source["public_44fz_application_securities"]:
        print(
            "FIRST_PARTY_BID_BOND",
            item["source_reg_number"],
            item["application_security_amount_rub"],
            "RUB",
            "legal_go",
            item["eligible_to_bid"],
        )


if __name__ == "__main__":
    main()
