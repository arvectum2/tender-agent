"""Strict append-only import of SIBUR 2128160/1: 6 kV BSK DESIGN, not sale."""
import argparse
import hashlib
import json
import os
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)

CID = "commercial:2128160-1:lot1"
BACKUPS = Path("/Users/master/ArvectumSafe/backups/data-platform")


def stage(path, root=ROOT):
    m = json.loads(path.read_text())
    if (path.is_symlink() or m.get("schema_version") != "pq-sibur-6kv-design-originals/1"
            or m.get("canonical_id") != CID or m.get("procedure_id") != "2128160/1"
            or len(m.get("source_receipts", [])) != 4
            or any(m.get(k) is not False for k in
                   ("signed_supplier_verified", "paid_verified", "equipment_supply_verified"))):
        raise ValueError("Wrong case or source claims")
    root = root.resolve(strict=True)
    original, card, doc, drawings, urls = [], None, None, 0, set()
    for name in m["source_receipts"]:
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not name.endswith(".bin.json"):
            raise ValueError("Unsafe receipt")
        rp = (root / rel).resolve(strict=True)
        if root not in rp.parents or rp.is_symlink():
            raise ValueError("Receipt outside internal root")
        j = json.loads(rp.read_text())
        rel = Path(j["relative_file"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe original")
        fp = (root / rel).resolve(strict=True)
        if root not in fp.parents or fp.is_symlink():
            raise ValueError("Original outside root")
        raw = fp.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if (j["case_id"] != CID or j["http_status"] != 200
                or j["sha256"] != sha or j["bytes"] != len(raw)
                or not 1000 <= len(raw) <= 12_000_000):
            raise ValueError("Original integrity mismatch")
        u = urlsplit(j["source_url"])
        if u.scheme != "https" or u.hostname != "sibur.ru" or u.fragment or u.username or u.password or j["source_url"] in urls:
            raise ValueError("Not distinct official HTTPS original")
        urls.add(j["source_url"])
        if u.path == "/ru/procurement/buy/archive/":
            if parse_qs(u.query) != {"procedure": ["2128160/1"]}:
                raise ValueError("Wrong procedure filter")
            rows = [x for x in re.findall(r"<tr[^>]*>.*?</tr>", raw.decode("utf8", "replace"), re.DOTALL | re.IGNORECASE)
                    if "2128160/1" in x]
            if len(rows) != 1 or not all(s in rows[0] for s in ("Модернизация", "Нефтехимия")):
                raise ValueError("Wrong original procedure row")
            card = rows[0]
            tier = "official_sibur_procurement_card"
        elif re.fullmatch(r"/upload/tmp/example/[a-z0-9]+/[a-z0-9]+\.docx", u.path):
            with zipfile.ZipFile(fp) as z:
                if len(z.namelist()) > 120 or "word/document.xml" not in z.namelist():
                    raise ValueError("Unsafe DOCX")
                xml = z.read("word/document.xml")
                if len(xml) > 3_000_000:
                    raise ValueError("Oversized DOCX XML")
            node = ET.fromstring(xml)
            W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            text = " ".join(" ".join(n.text or "" for n in node.iter(W)).split())
            if not all(q in text for q in ("регулируемых БСК", "3 шт.", "БСК 6кВ", "РП-115, РП-116")):
                raise ValueError("6kV design/quantity not proved")
            doc = True
            tier = "official_6kv_bsk_design_spec"
        elif re.fullmatch(r"/upload/tmp/example/[a-z0-9]+/[a-z0-9]+\.pdf", u.path) and raw.startswith(b"%PDF"):
            drawings += 1
            tier = "official_design_drawing_unreviewed"
        else:
            raise ValueError("Unrecognized original")
        original.append({"url": j["source_url"], "sha256": sha, "source_tier": tier})
    if card is None or not doc or drawings != 2 or any(urlsplit(e["url"]).path not in card for e in original if "/upload/" in e["url"]):
        raise ValueError("Four card-linked original documents required")
    rec = {"canonical_id": CID, "procedure_id": "2128160/1", "family": "bsk",
           "scope": "engineering_design_only", "market_scope": "verified_6kv_design_not_equipment_supply",
           "procurement_regime": "commercial", "platform": "SIBUR", "publication_date": "2026-03-17",
           "customer": {"name": 'ООО «НПП «Нефтехимия»'}, "status": "bids_closed_award_unknown",
           "description": "ПИР модернизации РП-115/116, проектирование 3 регулируемых БСК 6 кВ",
           "technical_voltage_kv": 6, "planned_bsk_quantity": 3, "nmck_rub": None,
           "supplier_verified": False, "signed_supplier_verified": False, "paid_verified": False,
           "equipment_supply_verified": False, "realized_equipment_revenue_rub": None, "evidence": original}
    h = hashlib.sha256(CID.encode()).hexdigest()
    ch = hashlib.sha256(json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    meta = {"data_version": "sibur_6kv_design_20261029", "procurement_id": CID,
            "procedure_id": "2128160/1", "regime": "commercial", "family": "bsk",
            "scope": rec["scope"], "market_scope": rec["market_scope"], "status": rec["status"],
            "source_urls": [e["url"] for e in original],
            "source_tiers": [e["source_tier"] for e in original],
            "source_original_sha256": [e["sha256"] for e in original],
            "research_not_market_population": True, "winning_supplier_only_if_verified": None}
    row = {"cid": CID, "id": h[:48], "uri": "urn:arvectum:pq:procurement:" + h,
           "hash": ch, "record": rec, "metadata": meta,
           "record_metadata": {"research_version": meta["data_version"],
                               "source_content_hash": ch, "source_evidence_urls": meta["source_urls"]}}
    return [row], m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    rows, m = stage(a.manifest)
    before = snapshot()
    if any(before[k] != m["base_db_expected_records"] for k in ("rows", "unique", "records")):
        raise RuntimeError("Database count drift")
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "ids": [CID]}))
        return
    if not a.backup_manifest or not a.receipt or a.receipt.exists():
        raise RuntimeError("Fresh backup and new receipt required")
    bp = a.backup_manifest.resolve(strict=True)
    if bp.parent != BACKUPS or a.backup_manifest.is_symlink() or time.time() - bp.stat().st_mtime > 1800:
        raise RuntimeError("Backup outside internal APFS or stale")
    backup = verified_backup(bp)
    result = insert(rows, before["rows"])
    receipt = {"schema_version": "pq-sibur-6kv-design-db-receipt/1",
               "before": before, **result, "backup_sha256": backup["sha256"],
               "source_manifest_sha256": hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
               "new_unique_lots": 1, "new_6kv_design_only": 1,
               "new_signed_suppliers": 0, "new_verified_equipment_sales_rub": 0}
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.receipt.with_name("." + a.receipt.name + ".partial")
    with tmp.open("x") as f:
        f.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, a.receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
