"""Source-bound append of Tatneft B2B 4469608 / EIS 32616065155 lot 7.

The 11-position parent NMC is not PQ market volume, and >1 kV does not
establish equipment nominal voltage within 6–35 kV.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)

CID = "223fz:32616065155:lot7"
URL = ("https://www.b2b-center.ru/market/"
       "postavka-elektrotekhnicheskogo-oborudovaniia-vykliuchateli/tender-4469608/")


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(root: Path, relative: str, expected_sha256: str) -> str:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or (root / rel).is_symlink():
        raise ValueError("Unsafe first-party original path")
    path = (root / rel).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise ValueError("Original escaped source root")
    raw = path.read_bytes()
    if not 30_000 <= len(raw) <= 2_000_000:
        raise ValueError("Original HTML exceeds bounded size")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("First-party original SHA256 mismatch")
    parser = Visible()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def stage(manifest: Path, *, source_root: Path = ROOT):
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("Unsafe source manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (data.get("schema_version") != "pq-tatneft-b2b-lot-primary/1"
            or data.get("canonical_id") != CID
            or data.get("eis_notice") != "32616065155"
            or data.get("b2b_procedure") != "4469608"
            or data.get("actual_b2b_lot") != 7
            or data.get("parent_number_of_positions") != 11
            or data.get("main_url") != URL
            or data.get("positions_url") != URL + "?action=positions"
            or data.get("pq_position_limit_rub_gross") != "3172000.00"
            or data.get("parent_limit_rub_gross") != "199598002.40"
            or data.get("pq_position_vat_pct") != 22
            or data.get("pq_position_units") != 1
            or data.get("pq_position_unit") != "компл"
            or data.get("pq_position_okpd2") != "27.12.10.190"
            or data.get("equipment_nominal_voltage_kv") is not None
            or data.get("original_detailed_technical_spec_read") is not False
            or data.get("winner_verified") is not False
            or data.get("signed_supplier_verified") is not False
            or data.get("paid_amount_verified") is not False
            or data.get("actual_equipment_sale_rub") is not None):
        raise ValueError("Source identity, lot number, scope, or price guard")
    root = source_root.resolve(strict=True)
    main = _text(root, data["main_original_relative"], data["main_html_sha256"])
    positions = _text(root, data["positions_original_relative"],
                      data["positions_html_sha256"])
    for item in ("32616065155", "4469608", "199 598 002,40",
                 'ООО "ТН - ЭНЕРГОСБЫТ"', "Результаты процедуры скрыты"):
        if item not in main:
            raise ValueError("Missing original parent procurement evidence: " + item)
    for item in ("Лот №7. Установки конденсаторные", "3 172 000,00",
                 "НДС: 22%", "на напряжение более 1 кВ"):
        if item not in positions:
            raise ValueError("Missing primary original lot7 evidence: " + item)
    if not re.search(r"Лот №7\. Установки конденсаторные.{0,550}3 172 000,00",
                     positions):
        raise ValueError("Lot7 per-lot ceiling not independently attributable")
    digest = hashlib.sha256(CID.encode()).hexdigest()
    row = {
        "id": "pq-tatneft-4469608-223fz-32616065155-lot7",
        "canonical_id": CID, "procedure_id": "32616065155", "lot_number": 7,
        "joint_notice_id": "32616065155", "b2b_procedure_id": "4469608",
        "family": "capacitor_bank", "scope": "equipment_supply_request",
        "market_scope": "nominal_voltage_over_1kv_strict_6_35kv_unverified",
        "procurement_regime": "223-fz", "platform": "B2B-Center / EIS 223-FZ",
        "publication_date": "2026-05-29",
        "customer": {"name": data["customer"]},
        "organizer": {"name": data["organizer"]},
        "description": "Лот №7. Установки конденсаторные, 1 комплект из 11 позиций",
        "status": "archived_outcome_hidden_by_organizer",
        "quantity": 1, "quantity_unit": "компл", "okpd2": "27.12.10.190",
        "equipment_nominal_voltage_kv": None,
        "okpd_category_voltage_over_1kv": True,
        "nmck_rub": "3172000.00", "nmck_vat_rate_pct": 22,
        "reported_price_kind": "per_lot_ceiling_with_vat_not_awarded_price",
        "parent_nmck_rub": "199598002.40", "parent_number_of_lots": 11,
        "supplier_verified": False, "signed_supplier_verified": False,
        "paid_verified": False, "realized_equipment_revenue_rub": None,
        "evidence": [
            {"url": URL, "sha256": data["main_html_sha256"],
             "source_tier": "original_public_b2b_notice"},
            {"url": URL + "?action=positions",
             "sha256": data["positions_html_sha256"],
             "source_tier": "original_public_b2b_position_table"},
        ],
    }
    value = json.dumps(row, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()
    h = hashlib.sha256(value).hexdigest()
    urls = [URL, URL + "?action=positions"]
    metadata = {
        "data_version": "tatneft_primary_lot7_20261029",
        "procurement_id": CID, "procedure_id": "32616065155",
        "family": "capacitor_bank", "scope": row["scope"],
        "market_scope": row["market_scope"], "status": row["status"],
        "nmck_rub": "3172000.00", "source_urls": urls,
        "source_tiers": ["original_public_b2b_notice",
                         "original_public_b2b_position_table"],
        "source_original_sha256": [data["main_html_sha256"],
                                   data["positions_html_sha256"]],
        "winning_supplier_only_if_verified": None,
        "research_not_market_population": True,
    }
    return {
        "cid": CID, "id": digest[:48],
        "uri": "urn:arvectum:pq:procurement:" + digest,
        "hash": h, "record": row, "metadata": metadata,
        "record_metadata": {
            "research_version": metadata["data_version"],
            "source_content_hash": h, "source_evidence_urls": urls,
        },
    }, data


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--backup-manifest", type=Path)
    cli.add_argument("--receipt", type=Path)
    args = cli.parse_args()
    row, source = stage(args.manifest)
    before = snapshot()
    if any(before[key] != source["base_unique_lots"] for key in
           ("rows", "unique", "records")):
        raise RuntimeError("Database corpus drift or already imported lot")
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "unique_lots_before": before["rows"],
                          "staged": row["cid"]}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt or args.receipt.is_symlink():
        raise ValueError("Apply requires verified full database backup and receipt")
    backup = verified_backup(args.backup_manifest)
    after = insert([row], expected=before["rows"])
    receipt = {
        "schema_version": "pq-tatneft-primary-db-import/1",
        "before": before, **after, "new_unique_lots": 1,
        "parent_lots": 11, "verified_new_6_35kv_equipment_lots": 0,
        "verified_sales_rub": 0, "verified_signed_suppliers": 0,
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "backup_sha256": backup["sha256"],
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
