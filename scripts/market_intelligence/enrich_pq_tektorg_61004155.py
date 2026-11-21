"""Null-only source-bound 6 kV UKRM technical field enrichment; not an award."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_docx_fields import docx_text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "commercial:РН61004155:lot1"
URL = "https://www.tektorg.ru/rosneft/procedures/20068407"
DIR = "captures/commercial___61004155_lot1/"
CARD = "20261031T123732761220Z-f1c46bab-76c7de4a9bbaec9f.bin"
ARCHIVE = "20261031T123808837025Z-43d86e35-8d534d2a2de2339f.bin"
CSHA = "76c7de4a9bbaec9feeefdfa9158732faa1d64df033f2a6812f998531ed3ec359"
ASHA = "8d534d2a2de2339f0c3e495b0d81accf4d285b3d58a405dc9cabef10f03c368b"
MEMBERS = {
    "Блок 7. Техническое задание/26073435 УКРМ-6-1-А450-3х150-Л0Н2Х6/ЕТТ УКРМ.docx":
        "6d37139ab89e13db77dd75b38a67d88f4609e54b4d36795d1ec0fdc0c6fd8b40",
    "Блок 7. Техническое задание/26088135 УКРМ-6-1-Р900-450+2х225-Л0Н2Х6/BP4-06-03_ETT-0151_IZM1.docx":
        "39444936857bf82aa9392fc536d785267dc62676513e7255d34629c9fbcc6156",
}
FIELDS = {"voltage_kv": "6",
          "power": "450 кВАр (3×150) / 900 кВАр (450+2×225); исполнения, не сумма поставки"}
OLD = "194f8257393b718f4b58099973adaaef3fc287956f4347c9887fc21fa0fb6505"


def original(name, sha):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS only")
    rel = DIR + name
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 12_000_000:
        raise ValueError("Unsafe source path")
    raw = p.read_bytes()
    rec = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != sha or rec["sha256"] != sha
            or rec["case_id"] != CID or rec["relative_file"] != rel
            or rec["http_status"] != 200):
        raise ValueError("Source SHA/receipt mismatch")
    return raw, rec, p


def verify():
    card, c, _ = original(CARD, CSHA)
    archive, a, p = original(ARCHIVE, ASHA)
    if c["source_url"] != URL or not archive.startswith(b"7z\xbc\xaf\x27\x1c"):
        raise ValueError("Source type mismatch")
    m = re.search(rb'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', card, re.DOTALL)
    if not m:
        raise ValueError("No official JSON")
    item = json.loads(m[1])["props"]["pageProps"]["procedureItem"]
    if (item["id"] != 20068407 or item["remoteId"] != 1196770
            or item["registryNumber"] != "РН61004155" or item["inn"] != "0277106840"
            or item["statusName"] != "Приём заявок" or item["protocols"]
            or len(item["lots"]) != 1 or item["lots"][0]["id"] != 23473272
            or not any(d["filename"] == "ДОЗ_БНД-0237-2026.7z"
                       and d["httpLink"] == a["source_url"] for d in item["documents"])):
        raise ValueError("Official procedure/doc mismatch")
    listing = subprocess.run(["/opt/homebrew/bin/7z", "l", "-slt", str(p)],
                             capture_output=True, text=True, check=True, timeout=20).stdout
    names = re.findall(r"^Path = (.+)$", listing, re.MULTILINE)
    if (len(names) > 100 or len(names) != len(set(names))
            or "Encrypted = +" in listing or any(names.count(n) != 1 for n in MEMBERS)):
        raise ValueError("Unsafe 7z archive")
    for name, sha in MEMBERS.items():
        raw = subprocess.run(["/opt/homebrew/bin/7z", "x", "-so", str(p), name],
                             capture_output=True, check=True, timeout=20).stdout
        if len(raw) > 1_000_000 or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("DOCX SHA mismatch")
        text = docx_text(raw)
        if "Номинальное напряжение главных цепей" not in text or "450+2х225" not in text:
            raise ValueError("ETT context mismatch")
    return {"card_url": URL, "card_sha256": CSHA, "archive_sha256": ASHA,
            "archive_receipt": DIR + ARCHIVE + ".json", "members": MEMBERS,
            "quantity_verified": False, "winner_verified": False,
            "supplier_verified": False, "payment_verified": False}


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent" or row["rev"] != 2
            or row["hash"] != OLD or digest(d) != OLD
            or d.get("canonical_id") != CID or d.get("procedure_id") != "РН61004155"
            or d.get("scope") != "supply" or d.get("customer", {}).get("inn") != "0277106840"
            or d.get("quantity") is not None
            or any(d.get(k) is not None for k in FIELDS)
            or "tektorg_ukrm_6kv_enrichment" in row["meta"]):
        raise RuntimeError("Owner/identity/old-null CAS mismatch")


def write(row, before, proof):
    data = {**row["data"], **FIELDS}
    data["evidence"] = [*data.get("evidence", []), {
        "url": URL, "sha256": CSHA,
        "source_tier": "first_party_tektorg_SHA_bound_technical_archive",
        "technical_archive_sha256": ASHA,
        "excerpt": "УКРМ-6-1-А450-3х150; УКРМ-6-1-Р900-450+2х225",
    }]
    h = digest(data)
    meta = {**row["meta"], "source_content_hash": h,
            "tektorg_ukrm_6kv_enrichment": {
                **proof, "fields": FIELDS, "previous_hash": OLD, "previous_revision": 2}}
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
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{OLD}'
AND d.revision=2 AND (d.data->'voltage_kv') IS NULL
AND (d.data->'power') IS NULL AND (d.data->>'quantity') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ CAS mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,
updated_at=now() FROM dp_resources r WHERE d.resource_id=r.resource_id
AND r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{OLD}'
AND d.revision=2 AND (d.data->'voltage_kv') IS NULL AND (d.data->'power') IS NULL;
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{OLD}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision=3 AND d.data->>'voltage_kv'='6'
AND d.metadata->'tektorg_ukrm_6kv_enrichment'->>'archive_sha256'='{ASHA}')<>1
THEN RAISE EXCEPTION 'PQ readback mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != 3
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postwrite readback mismatch")
    return {"case": CID, "before": before, "after": after, "new_verified_fields": 2,
            "fields": FIELDS, "old_hash": OLD, "new_hash": h, "proof": proof}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    proof, before, row = verify(), snapshot(), get_row(CID)
    validate(row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "fields": FIELDS, "proof": proof}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and unique receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal APFS acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if not backup["pg_restore_list_verified"] or not 0 <= age <= 1800:
        raise RuntimeError("Fresh verified backup required")
    result = write(row, before, proof)
    result["backup_sha256"] = backup["sha256"]
    with a.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
