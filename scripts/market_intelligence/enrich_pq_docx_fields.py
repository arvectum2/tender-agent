"""Atomic, source-SHA-bound P2 field enrichment from EIS RAR-contained DOCX."""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
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
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RULES = {
    "quantity": (r"Количество:\s*(\d{1,5})\s*шт", lambda s: int(s)),
    "voltage_kv": (r"Напряжение номинальное, кВ\s*(\d{1,3}[,.]\d+)", lambda s: str(float(s.replace(",", ".")))),
    "power": (r"Номинальная мощность, кВАр\s*(\d{1,7})", lambda s: f"{int(s)} кВАр"),
}


def docx_text(raw):
    if len(raw) > 5_000_000:
        raise ValueError("DOCX size")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        if len(names) > 300 or len(names) != len(set(names)) or "word/document.xml" not in names:
            raise ValueError("DOCX members")
        if z.getinfo("word/document.xml").file_size > 3_000_000:
            raise ValueError("XML size")
        xml = z.read("word/document.xml")
    return re.sub(r"\s+", " ", " ".join(e.text or "" for e in ET.fromstring(xml).iter(NS + "t"))).strip()


def verify_fields(fields, text):
    if set(fields) != set(RULES):
        raise ValueError("P2 fields mismatch")
    for key, (pattern, parse) in RULES.items():
        quote = fields[key]["exact_original_quote"]
        if len(quote) < 18 or quote not in text:
            raise ValueError(f"Original quote absent: {key}")
        matches = re.findall(pattern, quote)
        if len(matches) != 1 or parse(matches[0]) != fields[key]["value"]:
            raise ValueError(f"Original does not prove value: {key}")


def prepare(path):
    m = json.loads(path.read_text(encoding="utf-8"))
    cid = m["canonical_id"]
    if (m.get("schema_version") != "pq-docx-field-enrichment/1"
            or not re.fullmatch(r"223fz:[0-9]{11}:lot[1-9][0-9]*", cid)
            or not re.fullmatch("[a-f0-9]{64}", m["expected_content_hash"])
            or type(m["expected_revision"]) is not int):
        raise ValueError("Invalid manifest identity")
    root = ROOT.resolve(strict=True)
    if root != INTERNAL:
        raise ValueError("External evidence root forbidden")
    rel = Path(m["source_relative"])
    if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "captures":
        raise ValueError("Unsafe source path")
    source = (root / rel).resolve(strict=True)
    if root not in source.parents or source.is_symlink() or source.stat().st_size > 12_000_000:
        raise ValueError("Unsafe source archive")
    if hashlib.sha256(source.read_bytes()).hexdigest() != m["source_sha256"]:
        raise ValueError("Archive SHA drift")
    member = m["member_name"]
    if not member.endswith(".docx") or "/" in member or "\\" in member or len(member) > 200:
        raise ValueError("Unsafe DOCX member")
    listing = subprocess.run(["/usr/bin/bsdtar", "-tf", str(source)], capture_output=True, check=True, timeout=20)
    names = listing.stdout.decode("utf-8").splitlines()
    if len(names) > 150 or names.count(member) != 1:
        raise ValueError("DOCX member not unique")
    docx = subprocess.run(["/usr/bin/bsdtar", "-xOf", str(source), member],
                          capture_output=True, check=True, timeout=20).stdout
    if hashlib.sha256(docx).hexdigest() != m["member_sha256"]:
        raise ValueError("Contained DOCX SHA drift")
    verify_fields(m["fields"], docx_text(docx))
    return m


def validate(m, row):
    if row["id"] != m["canonical_id"] or row["owner"] != "tender-agent":
        raise RuntimeError("Identity/owner mismatch")
    if row["hash"] != m["expected_content_hash"] or row["rev"] != m["expected_revision"]:
        raise RuntimeError("CAS mismatch")
    if digest(row["data"]) != row["hash"]:
        raise RuntimeError("Data SHA drift")
    if any(row["data"].get(key) is not None for key in RULES):
        raise RuntimeError("Conflicting nonempty field")
    if not any(e.get("url") == m["source_url"] and e.get("sha256") == m["source_sha256"]
               for e in row["data"].get("evidence", [])):
        raise RuntimeError("Source not bound to lot")
    if "docx_field_enrichment" in row["meta"]:
        raise RuntimeError("Prior enrichment")


def update(m, row, before):
    cid = m["canonical_id"]
    data = {**row["data"], **{key: obj["value"] for key, obj in m["fields"].items()}}
    new_hash = digest(data)
    meta = {**row["meta"], "source_content_hash": new_hash,
            "docx_field_enrichment": {
                "fields": m["fields"], "source_sha256": m["source_sha256"],
                "member_sha256": m["member_sha256"], "source_url": m["source_url"],
                "previous_hash": row["hash"], "previous_revision": row["rev"]}}
    absent = " AND ".join(f"(d.data->'{key}') IS NULL" for key in RULES)
    present = " AND ".join(f"d.data->'{key}'={js(obj['value'])}" for key, obj in m["fields"].items())
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
 WHERE r.collection_id='{COL}' AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
 AND d.revision={row['rev']} AND {absent})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)}, metadata={js(meta)},
 revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {absent};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{cid}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev']+1} AND {present}
 AND d.metadata->'docx_field_enrichment'->>'source_sha256'='{m['source_sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(cid)
    if (any(before[k] != after[k] for k in ("rows", "unique", "records"))
            or actual["hash"] != new_hash or actual["rev"] != row["rev"] + 1
            or any(actual["data"].get(k) != v["value"] for k, v in m["fields"].items())):
        raise RuntimeError("Postcommit readback mismatch")
    return {"canonical_id": cid, "before": before, "after": after,
            "new_verified_fields": len(m["fields"]), "source_sha256": m["source_sha256"],
            "old_hash": row["hash"], "new_hash": new_hash}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    m = prepare(a.manifest)
    before = snapshot()
    row = get_row(m["canonical_id"])
    validate(m, row)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "case": m["canonical_id"],
                          "fields": m["fields"], "db": before}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and unique receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, timeout=60, check=True)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh verified full backup required")
    result = update(m, row, before)
    result["backup_sha256"] = backup["sha256"]
    result["manifest_sha256"] = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
