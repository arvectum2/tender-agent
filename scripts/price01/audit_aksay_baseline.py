"""Read-only PRICE-01 Aksay snapshot from already stored local original evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.procurement_llm.audit_official_finals import (
    SPECS,
    _leaf_value,
    _local,
    audit_original,
)
from scripts.procurement_llm.source_recovery import inspect_final_eis_protocol
from src.tender_research.competitive_bid_protocol import (
    AKSAY_ZIP_SHA256,
    build_aksay_baseline,
)


def verify_original_bid_rows(statistics_bytes: bytes, xml_bytes: bytes) -> int:
    """Compare all normalized exported bids to the original official XML rows.

    Original approved EIS source is separately SHA-checked, parsed without
    DOCTYPE/ENTITY. Rejection reason texts remain in private CSV/JSON, not Git.
    """
    if len(xml_bytes) > 32 * 1024 * 1024 or b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        raise ValueError("unsafe official EIS original XML")
    source = json.loads(statistics_bytes)
    bids = source["bids"]
    by_id = {str(x["application_id"]): x for x in bids}
    if len(by_id) != len(bids):
        raise ValueError("duplicate IDs in normalized source")
    root = ET.fromstring(xml_bytes)
    observed = {}
    for node in root.iter():
        if _local(node.tag) != "applicationInfo":
            continue
        identity = _leaf_value(node, "appNumber")
        price = _leaf_value(node, "finalPrice")
        is_admitted = _leaf_value(node, "admitted")
        rank = _leaf_value(node, "appRating")
        if not identity or price is None or is_admitted not in {"true", "false"}:
            raise ValueError("incomplete original EIS bid row")
        if identity in observed:
            raise ValueError("duplicate original EIS application ID")
        observed[identity] = (Decimal(price), is_admitted == "true", rank)
    if set(observed) != set(by_id):
        raise ValueError("original EIS and JSON application IDs differ")
    for identity, (price, admitted, rank) in observed.items():
        item = by_id[identity]
        if Decimal(str(item["price_rub"])) != price:
            raise ValueError("original EIS and JSON price differ")
        if (item["status"] == "admitted") != admitted:
            raise ValueError("original EIS and JSON admissibility differ")
        if (int(rank) if rank else None) != item["rank"]:
            raise ValueError("original EIS and JSON official rank differ")
    return len(observed)


def collect(*, source_dir: Path, archive: Path) -> dict:
    stats = (source_dir / "protocol_2026-10-14_statistics.json").read_bytes()
    bids = (source_dir / "protocol_2026-10-14_bids.csv").read_bytes()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != AKSAY_ZIP_SHA256:
        raise ValueError("official EIS original archive SHA mismatch")
    report = build_aksay_baseline(
        statistics_bytes=stats, csv_bytes=bids, official_archive_sha256=AKSAY_ZIP_SHA256,
    )
    spec = next(x for x in SPECS if x.registry == report["procurement_number"])
    audit_original(archive, spec)
    original = inspect_final_eis_protocol(archive, spec.registry, spec.application)
    with ZipFile(archive) as evidence:
        xml_bytes = evidence.read(original["protocol_member"])
    if hashlib.sha256(xml_bytes).hexdigest() != spec.xml_sha256:
        raise ValueError("official original EIS protocol XML SHA mismatch")
    report["official_protocol_xml_sha256"] = spec.xml_sha256
    report["original_bid_rows_individually_cross_checked"] = verify_original_bid_rows(
        stats, xml_bytes,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--official-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = collect(source_dir=args.source_dir, archive=args.official_zip)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("AKSAY", report["bids_total"], report["admitted_count"],
          "WINNER", report["winner"]["price_rub"], "OUR_RANK", report["arvectum_bid"]["rank"],
          "COST_SCENARIOS", report["cost_break_even_scenarios"])


if __name__ == "__main__":
    main()
