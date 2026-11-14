"""Fail-closed append of an original B2B-Center UKRM card; unknown voltage stays unknown."""
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


class Visible(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def stage(manifest: Path, source_root: Path = ROOT) -> tuple[dict, dict]:
    if manifest.is_symlink():
        raise ValueError("Unsafe manifest")
    m = json.loads(manifest.read_text(encoding="utf8"))
    if m.get("schema_version") != "pq-commercial-primary-source/1":
        raise ValueError("Invalid source schema")
    cid = m["canonical_id"]
    if not re.fullmatch(r"commercial:[0-9]{5,10}:lot1", cid):
        raise ValueError("Invalid procedure identity")
    number = cid.split(":")[1]
    url = m["primary_url"]
    if not re.fullmatch(
        rf"https://www\.b2b-center\.ru/market/[a-z0-9-]+/tender-{number}/", url
    ):
        raise ValueError("Wrong official primary URL")
    root = source_root.resolve(strict=True)
    rel = Path(m["private_source_relative"])
    file = (root / rel).resolve(strict=True)
    if rel.is_absolute() or ".." in rel.parts or root not in file.parents or (root / rel).is_symlink():
        raise ValueError("Unsafe original path")
    raw = file.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if not 1000 <= len(raw) <= 2_000_000 or sha != m["primary_source_sha256"]:
        raise ValueError("Original public card bytes differ")
    h = Visible()
    h.feed(raw.decode("utf8", errors="replace"))
    body = " ".join(" ".join(h.parts).split())
    if any(term not in body for term in (
        number, "Модернизация установки компенсации реактивной мощности",
        "ЭЛЬБРУС ДРИЛЛИНГ", "04.09.2025", "18.09.2025",
        "Всего заявок: 0", "признал процедуру несостоявшейся",
    )):
        raise ValueError("Original page does not support asserted facts")
    if (m["buyer"] != "ООО «ЭЛЬБРУС ДРИЛЛИНГ»" or m["bids_count"] != 0
            or m["result"] != "unsuccessful_no_bids"
            or m["voltage_kv"] is not None
            or m["technical_spec_original_verified"] is not False
            or m["signed_supplier_verified"] is not False):
        raise ValueError("Provisional record has unsupported claims")
    record = {
        "canonical_id": cid, "procedure_id": number,
        "family": "ukrm", "scope": "modernization_existing_equipment",
        "market_scope": "PQ_voltage_unconfirmed_not_strict_6_35kv",
        "procurement_regime": "commercial", "platform": "B2B-Center",
        "publication_date": "2025-09-04",
        "customer": {"name": m["buyer"]},
        "status": "unsuccessful_no_bids",
        "description": "Модернизация установки компенсации реактивной мощности (УКРМ)",
        "technical_voltage_kv": None, "nmck_rub": None,
        "bids_count": 0, "supplier_verified": False,
        "signed_supplier_verified": False, "paid_verified": False,
        "realized_equipment_revenue_rub": None,
        "evidence": [{"url": url, "source_tier": "primary_platform_original_public_card",
                      "sha256": sha}],
    }
    full = hashlib.sha256(cid.encode()).hexdigest()
    data = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(data).hexdigest()
    meta = {
        "data_version": "primary_commercial_20261029",
        "procurement_id": cid, "procedure_id": number,
        "regime": "commercial", "family": "ukrm",
        "scope": record["scope"], "market_scope": record["market_scope"],
        "status": record["status"],
        "source_urls": [url], "source_tiers": ["primary_platform_original_public_card"],
        "source_original_sha256": [sha], "research_not_market_population": True,
        "winning_supplier_only_if_verified": None,
    }
    return {
        "cid": cid, "id": full[:48],
        "uri": "urn:arvectum:pq:procurement:" + full,
        "hash": digest, "record": record, "metadata": meta,
        "record_metadata": {"research_version": meta["data_version"],
                            "source_content_hash": digest, "source_evidence_urls": [url]},
    }, m


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    row, source = stage(args.manifest)
    before = snapshot()
    if any(before[key] != source["baseline_lots"] for key in ("rows", "unique", "records")):
        raise RuntimeError("Corpus drift")
    if not args.apply:
        print(json.dumps({"before": before, "staged": row["cid"]}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise ValueError("Verified backup and receipt required")
    backup = verified_backup(args.backup_manifest)
    outcome = insert([row], expected=before["rows"])
    receipt = {"schema_version": "pq-commercial-original-import/1",
               "before": before, **outcome,
               "backup_sha256": backup["sha256"],
               "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
               "inserted_unique_lots": 1, "verified_strict_6_35kv_new_lots": 0,
               "new_signed_suppliers": 0, "new_verified_equipment_sales_rub": 0}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
