"""Source-bound, CAS-guarded enrichment of an absent PQ quantity field only."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def prepare(path, root=ROOT):
    m = json.loads(Path(path).read_text())
    cid = m["canonical_id"]
    if m.get("schema_version") != "pq-field-enrichment/1" or not re.fullmatch(
        r"(223fz|commercial):[^\s/\\]+:lot[1-9][0-9]*", cid
    ):
        raise ValueError("Invalid manifest/identity")
    if m.get("field") != "quantity" or type(m.get("value")) is not int or not 1 <= m["value"] <= 100000:
        raise ValueError("Only missing positive quantity supported")
    rel = Path(m["source_relative"])
    if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "captures":
        raise ValueError("Unsafe source path")
    root = Path(root).resolve(strict=True)
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 12000000:
        raise ValueError("Unsafe source")
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != m["source_sha256"]:
        raise ValueError("SHA drift")
    if len(m["exact_original_quote"]) < 15 or m["exact_original_quote"].encode() not in raw:
        raise ValueError("Quote not found in original")
    if not re.fullmatch("[a-f0-9]{64}", m["expected_content_hash"]):
        raise ValueError("Bad CAS hash")
    return m


def get_row(cid):
    if not re.fullmatch(r"(223fz|commercial):[^\s/\\]+:lot[1-9][0-9]*", cid):
        raise ValueError("Unsafe ID")
    out = psql(f"""BEGIN READ ONLY;
SELECT jsonb_build_object('id',r.external_id,'hash',r.content_hash,'rev',d.revision,
'data',d.data,'meta',d.metadata,'owner',c.owner)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
JOIN dp_collections c ON c.collection_id=r.collection_id
WHERE r.collection_id='{COL}' AND r.external_id='{cid}'; COMMIT;""")
    lines = [s for s in out.splitlines() if s.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError("Missing/duplicate lot")
    return json.loads(lines[0])


def validate(m, row):
    if row["id"] != m["canonical_id"] or row["owner"] != "tender-agent":
        raise RuntimeError("Wrong identity/owner")
    if row["hash"] != m["expected_content_hash"] or row["rev"] != m["expected_revision"]:
        raise RuntimeError("CAS drift")
    if digest(row["data"]) != row["hash"] or row["data"].get("quantity") is not None:
        raise RuntimeError("Content hash drift or quantity already set")
    if not any(e.get("url") == m["source_url"] and e.get("sha256") == m["source_sha256"]
               for e in row["data"].get("evidence", [])):
        raise RuntimeError("Source not bound to this lot")


def update(m, row, before):
    new_data = {**row["data"], "quantity": m["value"]}
    new_hash = digest(new_data)
    meta = {**row["meta"], "source_content_hash": new_hash}
    if "field_enrichment" in meta:
        raise RuntimeError("Conflicting enrichment")
    meta["field_enrichment"] = {
        "field": "quantity", "value": m["value"], "source_sha256": m["source_sha256"],
        "source_url": m["source_url"], "exact_original_quote": m["exact_original_quote"],
        "previous_content_hash": row["hash"], "previous_revision": row["rev"]}
    cid = m["canonical_id"]
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
 AND d.revision={row['rev']} AND (d.data->'quantity') IS NULL)<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(new_data)}, metadata={js(meta)},
 revision=revision+1, updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND (d.data->'quantity') IS NULL;
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{cid}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev']+1} AND d.data->>'quantity'='{m['value']}'
 AND d.metadata->'field_enrichment'->>'source_sha256'='{m['source_sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(cid)
    if (any(before[k] != after[k] for k in ("rows", "unique", "records"))
            or actual["hash"] != new_hash or actual["rev"] != row["rev"] + 1
            or actual["data"]["quantity"] != m["value"]):
        raise RuntimeError("Postcommit readback mismatch")
    return {"id": cid, "field": "quantity", "value": m["value"], "before": before,
            "after": after, "old_hash": row["hash"], "new_hash": new_hash,
            "source_sha256": m["source_sha256"], "new_verified_fields": 1}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--manifest", type=Path, required=True)
    a.add_argument("--apply", action="store_true")
    a.add_argument("--backup-manifest", type=Path)
    a.add_argument("--receipt", type=Path)
    args = a.parse_args()
    m = prepare(args.manifest)
    before = snapshot()
    row = get_row(m["canonical_id"])
    validate(m, row)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "id": m["canonical_id"], "before": before}))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Backup and receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Preflight blocked")
    backup = verified_backup(args.backup_manifest)
    result = update(m, row, before)
    result["backup_sha256"] = backup["sha256"]
    result["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
