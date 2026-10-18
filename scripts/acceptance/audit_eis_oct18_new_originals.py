"""Three source-attested October 18 EIS checks (one repeated Oct17 source ID); outputs metadata only.

No ETP mutations, no authenticated bids, no registered customer profile,
original ZIP and XML binaries are handled in ephemeral tempdir and discarded.
"""

import hashlib
import json
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)
from src.modules.tender_operator_agent_demo.settings import get_zakupki_soap_settings
from src.modules.tender_operator_agent_demo.zakupki_soap_client import ZakupkiSoapClient

# Fixed explicit read-only allowlist from the dated external discovery index.
NUMBERS = (
    "0163200000326005243",  # Smolensk Duma, website modifications
    "0332100025426000039",  # NGTU Univuz-3
    "0148200002426000013",  # Moscow region state information system
)
assert len(NUMBERS) == len(set(NUMBERS)) and all(
    re.fullmatch(r"\d{19}", n) for n in NUMBERS
)
settings = replace(get_zakupki_soap_settings(), timeout_seconds=12)
assert (
    settings.configured
    and settings.disable_proxy_for_eis
    and settings.require_direct_ru_route
)
client = ZakupkiSoapClient(settings, runtime_status_enabled=False)


def alltag(xml, key):
    vals = []
    for tag in xml.iter():
        if tag.tag.rsplit("}", 1)[-1] == key and (tag.text or "").strip():
            v = tag.text.strip()
            if v not in vals:
                vals.append(v)
    return vals


records = []
for number in NUMBERS:
    try:
        response = client.get_docs_by_reestr_number(number)
        if response.status != "completed":
            records.append(
                {
                    "number": number,
                    "archival_evidence": "UNAVAILABLE",
                    "reason": response.status,
                }
            )
            continue
        urls = response.archive_urls or (
            [response.archive_url] if response.archive_url else []
        )
        if len(urls) != 1 or not urls[0].startswith("https://int.zakupki.gov.ru/"):
            records.append(
                {"number": number, "archival_evidence": "UNVERIFIED_ARCHIVE_URL_COUNT"}
            )
            continue
        with tempfile.TemporaryDirectory(prefix="ta-44fz-source-research-") as folder:
            downloaded = client.download_archive(urls[0], Path(folder))
            archive = Path(folder) / downloaded.stored_name
            if not archive.is_file() or not 0 < archive.stat().st_size <= 8_000_000:
                records.append(
                    {"number": number, "archival_evidence": "UNVERIFIED_SIZE"}
                )
                continue
            zip_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            classified = classify_official_eis_archive(archive, number)
            version = classified.get("source_version")
            exact = None
            with zipfile.ZipFile(archive) as z:
                candidates = [
                    name
                    for name in z.namelist()
                    if name.startswith("epNotification")
                    and name.endswith(".xml")
                    and f"_{number}_{version}_" in name
                ]
                if len(candidates) != 1:
                    records.append(
                        {
                            "number": number,
                            "archival_evidence": "AMBIGUOUS_SELECTED_REVISION",
                            "candidate_notice_count": len(candidates),
                        }
                    )
                    continue
                raw = z.read(candidates[0])
                root = ET.fromstring(raw)
                if alltag(root, "purchaseNumber")[0] != number:
                    records.append(
                        {
                            "number": number,
                            "archival_evidence": "MISMATCH_NOTICE_REGISTRATION",
                        }
                    )
                    continue
                if hashlib.sha256(raw).hexdigest() != classified["notice_xml_sha256"]:
                    records.append(
                        {
                            "number": number,
                            "archival_evidence": "MISMATCH_CLASSIFIER_NOTICE_SHA",
                        }
                    )
                    continue
                title = alltag(root, "purchaseObjectInfo")
                end = alltag(root, "endDT")
                price = alltag(root, "maxPrice")
                published = alltag(root, "publishDTInEIS")
                if len(title) != 1 or len(end) != 1 or len(price) < 1:
                    records.append(
                        {
                            "number": number,
                            "archival_evidence": "AMBIGUOUS_FACTS",
                            "title_count": len(title),
                            "date_count": len(end),
                            "price_count": len(price),
                        }
                    )
                    continue
                dt = datetime.fromisoformat(end[0])
                if dt.tzinfo is None:
                    records.append(
                        {
                            "number": number,
                            "archival_evidence": "NAIVE_ARCHIVED_DEADLINE",
                        }
                    )
                    continue
                exact = {
                    "number": number,
                    "source_type": "OFFICIAL_EIS_SOAP_GETDOCSIP_ARCHIVED_ORIGINAL",
                    "archival_evidence": "SHA_VERIFIED_NOTICE",
                    "competitive_status": classified.get("status"),
                    "source_notice_type": classified.get("notice_type"),
                    "selected_archived_version": version,
                    "zip_sha256": zip_sha,
                    "zip_original_bytes": archive.stat().st_size,
                    "original_xml_sha256": hashlib.sha256(raw).hexdigest(),
                    "source_name": candidates[0],
                    "original_purchase_object": title[0][:450],
                    "source_archived_end_dt": end[0],
                    "archived_deadline_future_as_of_observation": dt
                    > datetime.now(UTC),
                    "source_archived_nmck_rub": price[0],
                    "source_publication": (published[0] if published else "UNKNOWN"),
                    "observed_at_utc": datetime.now(UTC).isoformat(),
                    "current_live_legal_status_verified": False,
                    "current_notice_latest_live_verified": False,
                    "full_attached_documents_verified": False,
                    "owner_qualified": False,
                    "bid_ready": False,
                    "etp_actions_executed": False,
                }
                records.append(exact)
    except Exception as exc:  # noqa: BLE001 - bounded official research records source unavailability
        records.append(
            {
                "number": number,
                "archival_evidence": "UNAVAILABLE",
                "reason": type(exc).__name__,
            }
        )
print(
    json.dumps(
        {
            "schema_version": "b2b-firstparty-44fz-new-original-20261018-v1",
            "audit_date": "2026-10-18",
            "read_only": True,
            "no_original_binaries_persisted": True,
            "current_legal_status_verified": False,
            "owner_bid_ready_count": 0,
            "records": records,
        },
        ensure_ascii=False,
        indent=2,
    )
)
