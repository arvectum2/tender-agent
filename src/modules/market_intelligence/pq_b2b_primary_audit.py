"""Recheck original B2B-Center source bytes and reject secondary outcome claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .pq_b2b_primary_capture import _final_url, _parse


def verify(*, source_root: Path, max_cases: int = 30) -> dict:
    if (source_root.is_symlink() or not source_root.is_dir()
            or not 1 <= max_cases <= 100):
        raise ValueError("Invalid original B2B public source directory")
    directories = sorted(
        p for p in source_root.iterdir()
        if p.is_dir() and not p.is_symlink()
        and re.fullmatch(r"[0-9]{7}", p.name)
        and (p / "receipt.json").is_file()
    )
    if len(directories) > max_cases:
        raise ValueError("B2B source budget would truncate audit")
    records = []
    for case in directories:
        p = case / "original-public-b2b.html"
        receipt = case / "receipt.json"
        if (p.is_symlink() or receipt.is_symlink() or not p.is_file()
                or p.stat().st_size > 400_000):
            raise ValueError("Missing original safe B2B document")
        row = json.loads(receipt.read_text(encoding="utf-8"))
        blob = p.read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        if (row.get("schema_version") != "pq-original-b2b-public-card/1"
                or row.get("procedure_id") != case.name
                or row.get("original_html_sha256") != sha
                or _final_url(case.name, str(row.get("source_url") or "")) != row.get("source_url")):
            raise ValueError("Source SHA/identity mismatch in B2B receipt")
        fresh = _parse(case.name, blob)
        for field in (
            "source_title", "source_description", "organizer_platform_display",
            "buyer_platform_display", "platform_status_text",
            "applications_count_not_qualified_bidders",
            "results_hidden_by_organizer", "replaces_reference_in_original_title",
            "subject_category",
        ):
            if row.get(field) != fresh[field]:
                raise ValueError("Original HTML and receipt source facts disagree")
        if (row.get("winner_verified") is not False
                or row.get("signed_contract_verified") is not False
                or row.get("signed_contract_supplier") is not None
                or row.get("contract_price_rub") is not None):
            raise ValueError("Public card cannot establish hidden winner or signed contract")
        records.append({
            "procedure_id": case.name,
            "source_url": row["source_url"],
            "original_sha256": sha,
            "source_title": fresh["source_title"],
            "source_description": fresh["source_description"],
            "organizer_platform_display": fresh["organizer_platform_display"],
            "buyer_platform_display": fresh["buyer_platform_display"],
            "platform_status_text": fresh["platform_status_text"],
            "applications_count_not_qualified_bidders": fresh[
                "applications_count_not_qualified_bidders"],
            "results_hidden_by_organizer": fresh["results_hidden_by_organizer"],
            "reference_to_replaced_tender": fresh[
                "replaces_reference_in_original_title"],
            "subject_category": fresh["subject_category"],
            "winner_verified": False,
            "signed_contract_verified": False,
            "contract_price_rub": None,
            "source_level": "original_first_party_etp_html_sha_verified",
        })
    return {
        "schema_version": "pq-original-b2b-audit/1",
        "first_party_cards_verified": len(records),
        "signed_contracts_verified": 0,
        "winner_identity_verified": 0,
        "source_records": records,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--originals", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(source_root=a.originals)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "source_records"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
