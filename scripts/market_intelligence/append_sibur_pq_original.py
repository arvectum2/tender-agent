"""Source-bound append-only SIBUR PQ notice, never an inferred sale."""
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scripts.market_intelligence.append_b2b_original_card import Visible
from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)

BACKUPS = Path("/Users/master/ArvectumSafe/backups/data-platform")


def stage(manifest: Path, root: Path = ROOT):
    m = json.loads(manifest.read_text(encoding="utf8"))
    if m.get("schema_version") != "pq-sibur-primary-incremental/1" or len(m.get("cases", [])) != 1:
        raise ValueError("Bad SIBUR manifest")
    c = m["cases"][0]
    cid = c["canonical_id"]
    match = re.fullmatch(r"commercial:([0-9]{7})-([2-9]):lot1", cid)
    if not match or c["procedure_id"] != f"{match[1]}/{match[2]}":
        raise ValueError("Invalid canonical notice:lot identity")
    if (c["technical_voltage_kv"] != 10 or c["status"] != "bids_closed_outcome_unknown"
            or c["signed_supplier_verified"] is not False or c["paid_verified"] is not False
            or c["scope"] != "10kv_compensation_equipment_or_works_unspecified"
            or c["market_scope"] != "10kv_primary_title_only_no_sale"
            or c["related_predecessor_procedure"] != f"{match[1]}/1"):
        raise ValueError("Unsupported source, voltage or economic outcome")
    root = root.resolve(strict=True)
    originals, seen, official_row = [], set(), None
    for name in c["source_receipts"]:
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not name.endswith(".bin.json"):
            raise ValueError("Unsafe receipt path")
        rp = (root / rel).resolve(strict=True)
        if root not in rp.parents or rp.is_symlink():
            raise ValueError("Receipt outside internal root")
        receipt = json.loads(rp.read_text(encoding="utf8"))
        if receipt.get("schema_version") != "pq-primary-immutable-capture/1" or receipt.get("case_id") != cid:
            raise ValueError("Receipt case mismatch")
        raw_rel = Path(receipt["relative_file"])
        if raw_rel.is_absolute() or ".." in raw_rel.parts:
            raise ValueError("Unsafe original path")
        f = (root / raw_rel).resolve(strict=True)
        if root not in f.parents or f.is_symlink() or not f.is_file():
            raise ValueError("Original outside internal root")
        raw = f.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if (sha != receipt["sha256"] or len(raw) != receipt["bytes"]
                or receipt["http_status"] != 200 or not 32 <= len(raw) <= 12_000_000):
            raise ValueError("Original SHA/size/status drift")
        url = receipt["source_url"]
        u = urlsplit(url)
        if u.scheme != "https" or u.hostname != "sibur.ru" or u.username or u.password or u.fragment or url in seen:
            raise ValueError("Not unique official SIBUR HTTPS source")
        if u.path == "/ru/procurement/buy/archive/":
            if parse_qs(u.query) != {"procedure": [c["procedure_id"]]}:
                raise ValueError("Wrong archive procedure filter")
            parser = Visible()
            parser.feed(raw.decode("utf8", "replace"))
            visible = " ".join(" ".join(parser.parts).split())
            if not all(q in visible for q in c["exact_source_quotes"]):
                raise ValueError("Verbatim archive quotes missing")
            matching = [r for r in re.findall(r"<tr[^>]*>.*?</tr>", raw.decode("utf8", "replace"), re.DOTALL | re.IGNORECASE)
                        if c["procedure_id"] in r]
            if len(matching) != 1:
                raise ValueError("Exact SIBUR procedure row missing")
            official_row = matching[0]
            tier = "official_sibur_archive_card"
        elif re.fullmatch(r"/upload/tmp/example/[a-z0-9]+/[a-z0-9]+\.7z", u.path) and not u.query:
            if not raw.startswith(b"7z\xbc\xaf\x27\x1c"):
                raise ValueError("Not original 7z")
            tier = "official_7z_unreviewed"
        else:
            raise ValueError("Unrecognized official URL")
        seen.add(url)
        originals.append({"url": url, "sha256": sha, "source_tier": tier,
                          "verbatim_quotes": c["exact_source_quotes"] if tier.endswith("card") else []})
    if len(originals) != 3 or sum(e["source_tier"].endswith("card") for e in originals) != 1:
        raise ValueError("Need one official card and two original archives")
    if official_row is None or any(urlsplit(e["url"]).path not in official_row
                                   for e in originals if e["source_tier"] == "official_7z_unreviewed"):
        raise ValueError("Attachments not linked from exact official procedure row")
    record = {
        "canonical_id": cid, "procedure_id": c["procedure_id"],
        "family": "ukrm", "scope": c["scope"], "market_scope": c["market_scope"],
        "procurement_regime": "commercial", "platform": "SIBUR",
        "publication_date": c["publication_date"], "customer": {"name": c["buyer"]},
        "status": c["status"], "description": c["description"],
        "technical_voltage_kv": 10, "nmck_rub": None,
        "related_predecessor_procedure": c["related_predecessor_procedure"],
        "project_reference": c["project_reference"],
        "supplier_verified": False, "signed_supplier_verified": False,
        "paid_verified": False, "realized_equipment_revenue_rub": None,
        "technical_archive_review": "pending", "evidence": originals,
    }
    full = hashlib.sha256(cid.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    metadata = {
        "data_version": "sibur_source_bound_20261029", "procurement_id": cid,
        "procedure_id": c["procedure_id"], "regime": "commercial",
        "family": "ukrm", "scope": c["scope"], "market_scope": c["market_scope"],
        "status": c["status"], "source_urls": [e["url"] for e in originals],
        "source_tiers": [e["source_tier"] for e in originals],
        "source_original_sha256": [e["sha256"] for e in originals],
        "research_not_market_population": True, "winning_supplier_only_if_verified": None,
    }
    row = {"cid": cid, "id": full[:48], "uri": "urn:arvectum:pq:procurement:" + full,
           "hash": digest, "record": record, "metadata": metadata,
           "record_metadata": {"research_version": "sibur_source_bound_20261029",
                               "source_content_hash": digest,
                               "source_evidence_urls": metadata["source_urls"]}}
    return [row], m


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--manifest", required=True, type=Path)
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--backup-manifest", type=Path)
    cli.add_argument("--receipt", type=Path)
    args = cli.parse_args()
    rows, manifest = stage(args.manifest)
    before = snapshot()
    if any(before[k] != manifest["base_db_expected_records"] for k in ("rows", "unique", "records")):
        raise RuntimeError("DB count drift: no insert")
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "ids": [r["cid"] for r in rows]}))
        return
    if not args.backup_manifest or not args.receipt or args.receipt.exists():
        raise RuntimeError("Apply requires fresh backup and unused receipt")
    bp = args.backup_manifest.resolve(strict=True)
    if bp.parent != BACKUPS or args.backup_manifest.is_symlink() or time.time() - bp.stat().st_mtime > 1800:
        raise RuntimeError("Backup not fresh on internal APFS")
    backup = verified_backup(bp)
    result = insert(rows, before["rows"])
    receipt = {"schema_version": "pq-sibur-original-db-receipt/1",
               "before": before, **result, "backup_sha256": backup["sha256"],
               "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
               "new_unique_lots": 1, "new_10kv_title_verified_notice": 1,
               "new_signed_suppliers": 0, "new_verified_equipment_sales_rub": 0}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    temp = args.receipt.with_name("." + args.receipt.name + ".partial")
    with temp.open("x", encoding="utf8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(temp, args.receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
