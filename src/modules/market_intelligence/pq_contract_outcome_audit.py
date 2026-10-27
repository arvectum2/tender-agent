"""Source-grounded PQ contract outcome audit from official XML references.

Separates a price printed in a contract-registry XML from a signed contract,
supplier proof and an EPC equipment value. Never fills unknown fields from bids.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _money(text: str | None) -> str | None:
    if text is None or not re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", text):
        return None
    try:
        return f"{Decimal(text):.2f}"
    except InvalidOperation:
        return None


def _source_check(row: dict, contract_root: Path) -> str:
    """Check ZIP and member SHA of the materialized evidence."""
    try:
        archive = Path(row["source_archive"])
        if (archive.is_symlink() or not archive.is_file()
                or not archive.resolve().is_relative_to(contract_root.resolve())
                or archive.stat().st_size > 200_000_000):
            return "invalid_archive_path"
        archive_bytes = archive.read_bytes()
        if hashlib.sha256(archive_bytes).hexdigest() != row["source_archive_sha256"]:
            return "archive_sha_mismatch"
        with zipfile.ZipFile(archive) as z:
            name = row["source_xml_member"]
            if name not in z.namelist() or z.getinfo(name).file_size > 10_000_000:
                return "xml_member_missing_or_oversized"
            if hashlib.sha256(z.read(name)).hexdigest() != row["source_xml_sha256"]:
                return "xml_sha_mismatch"
    except (KeyError, OSError, ValueError, zipfile.BadZipFile):
        return "unreadable_source"
    return "local_xml_verified"


def _day_scan_matches(day_scan: dict | None) -> set[tuple[str, str, str]]:
    return {
        (str(m.get("notice")), str(m.get("registry")), str(m.get("source_xml_sha256")))
        for batch in (day_scan or {}).get("records", [])
        for m in batch.get("matches", [])
    }


def audit(*, leads_path: Path, contracts_path: Path, contract_root: Path,
          day_scan_path: Path | None = None) -> dict:
    leads = json.loads(leads_path.read_text(encoding="utf-8"))["records"]
    contracts = json.loads(contracts_path.read_text(encoding="utf-8"))
    matches = _day_scan_matches(json.loads(day_scan_path.read_text(encoding="utf-8"))
                                if day_scan_path else None)
    lookup = {str(r.get("procedure_id")): r for r in leads}
    records = []
    seen_contract_lots = set()
    for row in contracts["records"][:500]:
        number = str(row["procedure_id"])
        if number not in lookup:
            continue
        key = (row.get("contract_register_number"), row.get("lot_number"))
        if key in seen_contract_lots:
            # One registered contract/lot may be re-advertised; never count it twice.
            continue
        seen_contract_lots.add(key)
        root_status = _source_check(row, contract_root)
        direct_rub = _money(row.get("ruble_price_text"))
        source_price = _money(row.get("price_text"))
        recovered = _money(row.get("ruble_price_recovered_from_rub_currency"))
        if recovered is None and not direct_rub and (
            row.get("currency_code") == "RUB"
            and row.get("currency_numeric_code") == "643"):
            recovered = source_price
        currency_rub = row.get("currency_code") == "RUB" and row.get("currency_numeric_code") == "643"
        price_conflict = bool(row.get("revision_price_conflict"))
        if direct_rub and source_price and currency_rub and direct_rub != source_price:
            price_conflict = True
        rub = (direct_rub or recovered) if not price_conflict and currency_rub else None
        if root_status != "local_xml_verified":
            rub = None
        verified_day = (number, str(row.get("contract_register_number")),
                        str(row.get("source_xml_sha256"))) in matches
        records.append({
            "procedure_id": number,
            "canonical_id": lookup[number].get("canonical_id"),
            "family": lookup[number].get("family"),
            "scope": lookup[number].get("scope"),
            "lot": row.get("lot_number"),
            "register_number": row.get("contract_register_number"),
            "buyer": row.get("customer_name"),
            "buyer_inn": row.get("customer_inn"),
            "contract_date_field": row.get("contract_document_date"),
            "registry_status_code": row.get("record_status_code"),
            "protocol_document_number": row.get("protocol_document_number"),
            "currency_code": row.get("currency_code"),
            "registry_rub_price": rub,
            "registry_price_conflict": price_conflict,
            "source_integrity": root_status,
            "original_day_scan_correlated": verified_day,
            "revision_count": len(row.get("source_revisions", [])) or 1,
            "source_xml_sha256": row.get("source_xml_sha256"),
            "source_archive_sha256": row.get("source_archive_sha256"),
            "supplier": None,
            "winner": None,
            "signed_contract_verified": False,
            "supplier_verified": False,
            "equipment_only_amount": None,
            "reason_unsigned": "Registry XML alone does not prove signature or supplier",
        })
    return {
        "schema_version": "pq-contract-outcome-audit/1",
        "leads_total": len(leads),
        "distinct_contract_lots_matched": len(records),
        "contract_lots_with_verified_local_xml": sum(x["source_integrity"] == "local_xml_verified" for x in records),
        "contract_lots_correlated_with_original_day_scan": sum(x["original_day_scan_correlated"] for x in records),
        "contract_lots_with_rub_price": sum(x["registry_rub_price"] is not None for x in records),
        "signed_contracts_verified": 0,
        "suppliers_verified": 0,
        "scope_warning": "Only supplied locally archived 223-FZ XML; not market population, not procurement award statistics",
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    parser.add_argument("--contract-root", type=Path, required=True)
    parser.add_argument("--day-scan", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = audit(leads_path=args.leads, contracts_path=args.contracts,
                 contract_root=args.contract_root, day_scan_path=args.day_scan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in data.items() if k != "records"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
