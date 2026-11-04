"""One-case SHA-pinned P2 and bidder-offer enrichment; never a signed sale."""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
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

CID = "223fz:32616497692:lot1"
D = "captures/223fz_32616497692_lot1/"
DOC = D + "20261030T053735102348Z-9dafc726-66f2dec7487352c6.bin"
RTF = D + "20261030T233101607038Z-359485f0-c6fb6317471d1bc0.bin"
DS = "66f2dec7487352c6bba4e7f5f182a3e2a614c7310dfec9ac2b9e82ed87d7c834"
RS = "c6fb6317471d1bc0fff40d641152df09cacd734e188a4f12eb73153898eddbbb"
MS = "28982223fc3f30dba1eefbfd0cf2c23200a192621b0b11b3d4f2e2fbf3ff272a"
Z = "Извещение_о_закупке_5237.zip"
M = "Извещение о закупке_5237/Приложение № 2 Техническое задание/07. ТЗ ячейка+УКРМ Черные камни - v5.docx"
BIDDER = 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ПРОМЫШЛЕННАЯ КОМПАНИЯ "ВТОРАЛЮМИНПРОДУКТ"'
FIELDS = {"voltage_kv": "10.5", "power": "3150 кВАр", "bid": "79101498.40"}
QUOTES = {"voltage_kv": "Номинальное напряжение, кВ 10,5", "power": "Мощность, кВар 3150",
          "bid": "с предложенной ценой договора 79101498.4 RUB"}


def source(rel, sha):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise ValueError("Internal APFS required")
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 8000000:
        raise ValueError("Unsafe source")
    raw = p.read_bytes()
    r = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != sha or r["case_id"] != CID
            or r["sha256"] != sha or r["relative_file"] != rel or r["http_status"] != 200
            or not r["source_url"].startswith("https://rosseti.roseltorg.ru/file/get/")):
        raise ValueError("First-party receipt/SHA mismatch")
    return raw, r["source_url"]


def member(raw, name):
    if len(raw) > 8000000:
        raise ValueError("Oversize archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries = z.infolist()
        if len(entries) > 100 or len({e.filename for e in entries}) != len(entries):
            raise ValueError("Unsafe ZIP listing")
        if any(e.filename.startswith("/") or ".." in Path(e.filename).parts
               or e.file_size > 6000000 or e.file_size > max(e.compress_size, 1) * 250
               for e in entries):
            raise ValueError("Unsafe ZIP member")
        if sum(e.filename == name for e in entries) != 1:
            raise ValueError("Missing/duplicate member")
        return z.read(name)


def verify():
    archive, u1 = source(DOC, DS)
    rtf, u2 = source(RTF, RS)
    inner = member(member(archive, Z), M)
    if hashlib.sha256(inner).hexdigest() != MS or not rtf.startswith(b"{\\rtf1"):
        raise ValueError("DOCX/RTF mismatch")
    tech = docx_text(inner)
    offer = re.sub(r"\\'([0-9a-fA-F]{2})",
                   lambda m: bytes.fromhex(m[1]).decode("cp1251", "replace"),
                   rtf.decode("ascii", "replace"))
    if ("ПС 110 кВ Вяртсиля" not in tech or "32616497692" not in offer
            or BIDDER not in offer or not all(
                q in (offer if k == "bid" else tech) for k, q in QUOTES.items())):
        raise ValueError("Case/participant/quote mismatch")
    return {"source_urls": [u1, u2], "source_sha256": [DS, RS],
            "member_sha256": MS, "quotes": QUOTES, "participant": BIDDER,
            "role": "bidder_not_winner", "winner_proven": False,
            "signed_contract_proven": False}


def write(row, before, proof):
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or digest(row["data"]) != row["hash"]
            or any(row["data"].get(k) is not None for k in FIELDS)
            or row["meta"].get("roseltorg_field_enrichment")
            or not any("32616497692" in e.get("url", "")
                       for e in row["data"].get("evidence", []))):
        raise RuntimeError("Owner/identity/null-only CAS mismatch")
    data = {**row["data"], **FIELDS}
    new_hash = digest(data)
    meta = {**row["meta"], "source_content_hash": new_hash,
            "roseltorg_field_enrichment": {**proof, "fields": FIELDS,
                "previous_hash": row["hash"], "previous_revision": row["rev"]}}
    absent = " AND ".join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
    present = " AND ".join(f"d.data->'{k}'={js(v)}" for k, v in FIELDS.items())
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
 AND d.revision={row['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']} AND {absent};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev']+1} AND {present})<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != new_hash or actual["rev"] != row["rev"]+1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postwrite readback mismatch")
    return {"case": CID, "before": before, "after": after, "fields": FIELDS,
            "old_hash": row["hash"], "new_hash": new_hash, "proof": proof}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    proof, before, row = verify(), snapshot(), get_row(CID)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "case": CID, "db": before,
                          "fields": FIELDS, "proof": proof}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and exclusive receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, timeout=60, check=True)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Preflight blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh full backup required")
    result = write(row, before, proof)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
