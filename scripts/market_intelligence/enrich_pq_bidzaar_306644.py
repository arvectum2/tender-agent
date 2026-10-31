"""Null-only, SHA-verified P2 enrichment: Bidzaar 306-644 customer-owned UKRM."""
import argparse
import hashlib
import io
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from docx import Document

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "commercial:306-644:lot35"
CARD_URL = "https://bidzaar.com/app/process/light/019ce668-617b-7b1a-861e-113ed78182af"
CARD = ("20261031T153251690518Z-a330410d-26fd76ceffd9825f.bin",
        "26fd76ceffd9825fcfeb48e0c0a68fc51887acaf478084ce45ad2e3104cd666c")
DOC_URL = "https://bidzaar.com/api/filestorage/files/download/8042258e-bd58-4efc-9f98-b00db6113f82"
DOC = ("20261031T153316931658Z-74000cf4-28c970162cc7b36c.bin",
       "28c970162cc7b36cff91df3b64ea4168c5717cc43554aea162440e6d10272516")
FIELDS = {"voltage_kv": "6", "power": "900 кВАр на каждую из 2 УКРМ"}
QUOTES = ("Установить УКРМ 6 кВ. 900кВАр в количестве 2 шт.",
          "Установки компенсации реактивной мощности УКРМ 6 кВ. предоставляет заказчик.")


def source(spec, url):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("External source forbidden")
    rel = "captures/commercial_306-644_lot35/" + spec[0]
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 200 <= p.stat().st_size <= 1_000_000:
        raise RuntimeError("Unsafe source")
    raw = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != spec[1] or receipt["sha256"] != spec[1]
            or receipt["source_url"] != url or receipt["case_id"] != CID
            or receipt["relative_file"] != rel or receipt["http_status"] != 200):
        raise RuntimeError("Original SHA/receipt mismatch")
    return raw


def proof():
    card = source(CARD, CARD_URL).decode("utf-8", "replace")
    doc = Document(io.BytesIO(source(DOC, DOC_URL)))
    text = " ".join(p.text for p in doc.paragraphs)
    if not all(x in card for x in (CID.split(":")[1], "СИБСТЕКЛО", DOC_URL)):
        raise RuntimeError("Card identity mismatch")
    if not all(x in text for x in QUOTES):
        raise RuntimeError("Original DOCX quote mismatch")
    return {"url": DOC_URL, "sha256": DOC[1], "source_tier": "first_party_technical_docx",
            "excerpt": "; ".join(QUOTES)}


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("scope") != "epc"
            or d.get("family") != "ukrm" or d.get("customer", {}).get("name") != "СИБСТЕКЛО"
            or d.get("quantity") != 1 or d.get("quantity_unit") != "усл.ед"
            or digest(d) != row["hash"] or any(d.get(k) is not None for k in FIELDS)
            or not any(e.get("url") == CARD_URL for e in d.get("evidence", []))
            or "bidzaar_306644_p2" in row["meta"]):
        raise RuntimeError("Identity/owner/old-null CAS mismatch")


def prepared(row, evidence):
    d = {**row["data"], **FIELDS, "evidence": [*row["data"]["evidence"], evidence]}
    h = digest(d)
    m = {**row["meta"], "source_content_hash": h,
         "bidzaar_306644_p2": {"fields": FIELDS, "source_sha256": DOC[1],
         "card_sha256": CARD[1], "exact_quotes": QUOTES,
         "customer_provided_equipment": True, "physical_ukrm_units": 2,
         "not_an_equipment_sale": True, "old_hash": row["hash"], "old_revision": row["rev"]}}
    return d, m, h


def apply(row, evidence, before):
    d, m, h = prepared(row, evidence)
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
AND (d.data->'voltage_kv') IS NULL AND (d.data->'power') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ owner/count/CAS mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(m)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND (d.data->'voltage_kv') IS NULL AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND d.data->>'voltage_kv'='6'
AND d.data->>'power'='900 кВАр на каждую из 2 УКРМ'
AND d.metadata->'bidzaar_306644_p2'->>'source_sha256'='{DOC[1]}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch';END IF;END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != row["rev"] + 1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postcommit readback mismatch")
    return {"canonical_id": CID, "before": before, "after": after,
            "new_verified_fields": 2, "fields": FIELDS, "source_sha256": DOC[1]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    ev, row, before = proof(), get_row(CID), snapshot()
    validate(row)
    if not a.apply:
        print(json.dumps({"dry_run": True, "before": before, "fields": FIELDS}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Backup and receipt required")
    g = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                       capture_output=True, text=True, timeout=60, check=True)
    if json.loads(g.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    b = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(b["created_at_utc"])).total_seconds()
    if b.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh full verified backup required")
    out = apply(row, ev, before)
    out["backup_sha256"] = b["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

