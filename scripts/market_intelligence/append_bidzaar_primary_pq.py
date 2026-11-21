"""Source-bound import of one seven-site PQ-design Bidzaar tender, no sales inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.market_intelligence.append_pq_delta_20261029 import (
    ROOT,
    insert,
    snapshot,
    verified_backup,
)


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

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def source(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or (root / rel).is_symlink():
        raise ValueError("Unsafe original path")
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or not p.is_file():
        raise ValueError("Original outside corpus")
    return p


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) > 120 or "word/document.xml" not in z.namelist():
            raise ValueError("Unbounded or invalid DOCX")
        xml = z.read("word/document.xml")
        if len(xml) > 3000000:
            raise ValueError("Unbounded original XML")
    node = ET.fromstring(xml)
    return " ".join(n.text or "" for n in node.iter(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))


def stage(path, source_root=ROOT):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Unsafe manifest")
    m = json.loads(path.read_text(encoding="utf-8"))
    url = "https://bidzaar.com/app/process/light/019b4fe0-38ca-773a-91b0-0ff33daedb7d"
    if (m.get("schema_version") != "pq-bidzaar-multisite-originals/1"
        or m.get("canonical_id") != "commercial:281-705:lot1"
        or m.get("source_first_party_url") != url
        or m.get("lot_count") != 1 or m.get("positions") != 7
        or m.get("equipment_nominal_voltage_kv") is not None
        or m.get("signed_supplier_verified") is not False
        or m.get("named_winner_verified") is not False
        or m.get("equipment_sales_verified_rub") is not None
        or m.get("contract_price_verified_rub") is not None):
        raise ValueError("Source identity/uncertainty guard")
    root = source_root.resolve(strict=True)
    raw = source(root,m["source_first_party_html_relative"]).read_bytes()
    if not 1000 <= len(raw) <= 2000000 or hashlib.sha256(raw).hexdigest() != m["source_first_party_sha256"]:
        raise ValueError("Original platform HTML SHA")
    parser = Visible()
    parser.feed(raw.decode("utf8",errors="replace"))
    text = re.sub(r"\s+"," "," ".join(parser.parts))
    for phrase in ("281-705","Русагро","гармонических искажений","Спецификация по позициям (7)","24.12.2025","14.05.2026"):
        if phrase not in text:
            raise ValueError("First party card does not establish fact: "+phrase)
    attachments = m.get("original_docx")
    if not isinstance(attachments,list) or len(attachments)!=7:
        raise ValueError("Seven original technical documents required")
    hashes = set()
    protective_04 = 0
    ru6 = 0
    for d in attachments:
        if not re.fullmatch(r"https://bidzaar\.com/api/filestorage/files/download/[a-f0-9-]{36}",d["url"]):
            raise ValueError("Wrong first-party attachment URL")
        if d["url"] not in raw.decode("utf8",errors="replace"):
            raise ValueError("Attachment not linked on original card")
        p = source(root,d["private_relative"])
        payload = p.read_bytes()
        sha = hashlib.sha256(payload).hexdigest()
        if (not 1000 <= len(payload) <= 300000 or sha != d["sha256"]
            or len(payload) != d["size_bytes"] or sha in hashes):
            raise ValueError("Original attachment SHA/size/identity mismatch")
        txt = docx_text(p)
        if "гармоническ" not in txt.casefold() or "фильтр" not in txt.casefold():
            raise ValueError("Source DOCX is unrelated to PQ")
        protective_04 += bool(re.search(r"0[.,]4\s*кВ",txt,re.IGNORECASE))
        ru6 += "РУ6" in txt
        hashes.add(sha)
    if protective_04 < 5 or ru6 != 1:
        raise ValueError("Voltage uncertainty requires manual re-review")
    return m,hashes


def staged_row(m, hashes):
    cid = m["canonical_id"]
    url = m["source_first_party_url"]
    digest = hashlib.sha256(cid.encode()).hexdigest()
    record = {
        "id": "pq-2025-rusagro-harmonic-filter-7-site-design",
        "canonical_id": cid, "procedure_id": "281-705",
        "family": "harmonic_filters", "scope": "design_harmonic_filtration",
        "market_scope": "voltage_unverified_not_strict_6_35kv",
        "procurement_regime": "commercial", "platform": "Bidzaar",
        "publication_date": "2025-12-24", "date_basis": "first_party_public_card",
        "customer": {"name": "Русагро — сахарные заводы"},
        "status": "completed_request_award_not_verified",
        "description": "Проектирование мест установки фильтров гармоник и электрических схем семи сахарных заводов",
        "lot_count": 1, "positions": 7,
        "technical": {
            "nominal_filter_voltage_kv": None,
            "low_voltage_protection_mentioned_kv": 0.4,
            "ru6_location_mentioned_not_proof_of_filter_voltage": True,
        },
        "nmck_rub": None, "supplier_verified": False,
        "signed_supplier_verified": False, "paid_verified": False,
        "realized_equipment_revenue_rub": None,
        "original_docx_sha256": sorted(hashes),
        "evidence": [{"url": url, "sha256": m["source_first_party_sha256"],
                      "source_tier": "first_party_platform_public_card"}],
    }
    content = json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    ch = hashlib.sha256(content).hexdigest()
    metadata = {
        "data_version": "bidzaar_originals_20261029", "procurement_id": cid,
        "procedure_id": "281-705", "family": record["family"],
        "scope": record["scope"], "market_scope": record["market_scope"],
        "status": record["status"], "source_urls": [url],
        "source_tiers": ["first_party_platform_public_card"],
        "source_original_sha256": sorted(hashes) + [m["source_first_party_sha256"]],
        "research_not_market_population": True,
        "winning_supplier_only_if_verified": None,
    }
    return {
        "cid": cid, "id": digest[:48],
        "uri": "urn:arvectum:pq:procurement:"+digest,
        "hash": ch, "record": record, "metadata": metadata,
        "record_metadata": {
            "research_version": metadata["data_version"],
            "source_content_hash": ch, "source_evidence_urls": [url],
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--backup-manifest",type=Path)
    p.add_argument("--receipt",type=Path)
    args = p.parse_args()
    manifest, hashes = stage(args.manifest)
    row = staged_row(manifest, hashes)
    before = snapshot()
    if any(before[k] != manifest["baseline_unique_lots"] for k in ("rows","unique","records")):
        raise RuntimeError("Database count changed during research")
    if not args.apply:
        print(json.dumps({"mode":"dry_run","before":before,"add":row["cid"],
                          "originals_sha_verified":len(hashes)},ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt or args.receipt.is_symlink():
        raise ValueError("Full dump and receipt required")
    backup = verified_backup(args.backup_manifest)
    after = insert([row],expected=before["rows"])
    receipt = {
        "schema_version":"pq-bidzaar-source-bound-postgres-receipt/1",
        "before":before,**after,
        "source_manifest_sha256":hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "backup_sha256":backup["sha256"],"added_unique_lots":1,
        "independent_tender_positions":7,"original_docx_sha_verified":len(hashes),
        "new_confirmed_strict_6_35kv_equipment_sales":0,
        "new_confirmed_signed_suppliers":0,
    }
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False))


if __name__ == "__main__":
    main()
