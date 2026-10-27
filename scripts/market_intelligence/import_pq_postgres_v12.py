"""MI-013: guarded production Data Platform PostgreSQL importer.

Without --apply: only validates the 71-source v12 corpus and prints a plan.
--check-db: additionally performs read-only preflight checks.
--apply: requires explicit per-command owner authorization, a backup directory,
and the approved literal token MI013-71-20261027. No migrations or index writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from export_pq_data_platform import export_records
from materialize_pq_research_v12 import materialize

DATABASE = "arvectum_data"
CONTAINER = "arvectum-postgres"
COLLECTION = "arvectum-market-pq-6-35kv"
SOURCE = "market_intelligence_procurement_research"
ACK = "MI013-71-20261027"
BACKUP = Path("/Volumes/ArvectumSSD/Arvectum/repos/data-platform/scripts/ops/backup-postgres.sh")


def stage() -> list[dict]:
    rows = export_records(materialize())
    if len(rows) != 71 or len({r["resource_id"] for r in rows}) != 71:
        raise ValueError("expected 71 unique resource IDs")
    if len({r["external_id"] for r in rows}) != 71:
        raise ValueError("duplicate canonical ID")
    for item in rows:
        cid = item["external_id"]
        hexdigest = hashlib.sha256(cid.encode("utf-8")).hexdigest()
        if item["resource_id"] != hexdigest[:48]:
            raise ValueError("unstable resource ID")
        if item["canonical_uri"] != "urn:arvectum:pq:procurement:" + hexdigest:
            raise ValueError("invalid canonical URI")
        if item["collection_id"] != COLLECTION:
            raise ValueError("wrong collection")
        if item["status"] != "staged_unreviewed":
            raise ValueError("record prematurely reviewed")
        if not item["metadata"]["research_not_market_population"]:
            raise ValueError("market population conflated with examples")
        if not item["metadata"]["source_urls"]:
            raise ValueError("source evidence missing")
    return rows


def query(sql: str) -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker not available")
    process = subprocess.run(
        [docker, "exec", "-i", CONTAINER, "psql", "-X", "-A", "-t",
         "-v", "ON_ERROR_STOP=1", "-U", "arvectum", "-d", DATABASE],
        input=sql, text=True, capture_output=True, timeout=120,
    )
    if process.returncode:
        raise RuntimeError("PostgreSQL statement failed: " + process.stderr[-450:])
    return process.stdout


def inspect_target() -> dict:
    sql = (
        "BEGIN READ ONLY;\n"
        "SELECT current_database();\n"
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name IN "
        "('dp_collections','dp_resources','dp_records');\n"
        "SELECT count(*) FROM dp_resources "
        "WHERE collection_id='arvectum-market-pq-6-35kv';\n"
        "SELECT count(*) FROM dp_records WHERE resource_id IN "
        "(SELECT resource_id FROM dp_resources "
        "WHERE collection_id='arvectum-market-pq-6-35kv');\n"
        "COMMIT;\n"
    )
    values = [x.strip() for x in query(sql).splitlines() if x.strip()]
    if len(values) != 4 or values[0] != DATABASE or values[1] != "3":
        raise RuntimeError("Data Platform target schema not verified")
    return {
        "database": values[0],
        "required_tables": int(values[1]),
        "pq_resources": int(values[2]),
        "pq_records": int(values[3]),
    }


def build_apply_sql(rows: list[dict]) -> str:
    if len(rows) != 71:
        raise ValueError("unexpected source count")
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    hex_data = payload.encode("utf-8").hex()
    return f"""
BEGIN;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';
SELECT pg_advisory_xact_lock(hashtext('mi013-pq-71-v12'));
DO $guard$
BEGIN
 IF current_database() <> 'arvectum_data' THEN
    RAISE EXCEPTION 'wrong database';
 END IF;
 IF (SELECT count(*) FROM information_schema.tables WHERE
     table_schema='public' AND table_name IN
     ('dp_collections','dp_resources','dp_records')) <> 3 THEN
    RAISE EXCEPTION 'dp schema missing';
 END IF;
 IF EXISTS (SELECT 1 FROM dp_collections WHERE
    collection_id='arvectum-market-pq-6-35kv' AND owner<>'tender-agent') THEN
    RAISE EXCEPTION 'target collection is owned by another actor';
 END IF;
END $guard$;
CREATE TEMP TABLE mi013_stage(item jsonb NOT NULL) ON COMMIT DROP;
INSERT INTO mi013_stage
 SELECT value FROM jsonb_array_elements(
 convert_from(decode('{hex_data}', 'hex'), 'UTF8')::jsonb);
DO $guard$
BEGIN
 IF (SELECT count(*) FROM mi013_stage) <> 71 THEN
    RAISE EXCEPTION 'incorrect source item count';
 END IF;
 IF EXISTS (
   SELECT 1 FROM mi013_stage s JOIN dp_resources r
    ON r.resource_id=s.item->>'resource_id'
   WHERE r.collection_id<>'arvectum-market-pq-6-35kv'
      OR r.source_type<>'market_intelligence_procurement_research'
      OR r.canonical_uri<>s.item->>'canonical_uri'
 ) THEN RAISE EXCEPTION 'cross-tenant resource collision'; END IF;
 IF EXISTS (
   SELECT 1 FROM mi013_stage s JOIN dp_records r
    ON r.record_id='pq:'||(s.item->>'resource_id')
   WHERE r.resource_id<>s.item->>'resource_id'
      OR r.record_type<>'pq_procurement_notice_lot'
 ) THEN RAISE EXCEPTION 'record identity collision'; END IF;
END $guard$;
INSERT INTO dp_collections
 (collection_id,owner,name,default_language,access_policy,retention_policy,
  created_at,updated_at)
VALUES ('arvectum-market-pq-6-35kv','tender-agent',
        'Power Quality 6-35 kV market corpus MI-013', 'russian',
        '{{}}'::jsonb, '{{}}'::jsonb, now(),now())
ON CONFLICT (collection_id) DO NOTHING;
INSERT INTO dp_resources
 (resource_id,collection_id,source_type,canonical_uri,external_id,
  content_hash,status,metadata,refresh_policy,
  first_seen_at,last_seen_at,created_at,updated_at)
SELECT item->>'resource_id', 'arvectum-market-pq-6-35kv',
       'market_intelligence_procurement_research',
       item->>'canonical_uri',item->>'external_id',
       item->>'content_hash','staged_unreviewed',item->'metadata','{{}}'::jsonb,
       now(),now(),now(),now()
FROM mi013_stage
ON CONFLICT (resource_id) DO UPDATE
 SET content_hash=EXCLUDED.content_hash,
     metadata=EXCLUDED.metadata,
     status=EXCLUDED.status,
     updated_at=now(),last_seen_at=now()
 WHERE dp_resources.content_hash IS DISTINCT FROM EXCLUDED.content_hash
    OR dp_resources.metadata IS DISTINCT FROM EXCLUDED.metadata
    OR dp_resources.status IS DISTINCT FROM EXCLUDED.status;
INSERT INTO dp_records
 (record_id,resource_id,record_type,data,revision,review_status,
  metadata,created_at,updated_at)
SELECT 'pq:'||(item->>'resource_id'),item->>'resource_id',
       'pq_procurement_notice_lot',item->'source_record',1,'unreviewed',
       jsonb_build_object(
         'source_content_hash',item->>'content_hash',
         'source_evidence_urls',item->'metadata'->'source_urls',
         'research_version','v12'),now(),now()
FROM mi013_stage
ON CONFLICT (record_id) DO UPDATE
 SET data=EXCLUDED.data,metadata=EXCLUDED.metadata,
     revision=dp_records.revision+1,updated_at=now()
 WHERE dp_records.data IS DISTINCT FROM EXCLUDED.data
    OR dp_records.metadata IS DISTINCT FROM EXCLUDED.metadata;
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources
    WHERE collection_id='arvectum-market-pq-6-35kv')<>71 THEN
    RAISE EXCEPTION 'post-import resource count mismatch';
 END IF;
 IF (SELECT count(*) FROM dp_records WHERE resource_id IN
    (SELECT resource_id FROM dp_resources
      WHERE collection_id='arvectum-market-pq-6-35kv'))<>71 THEN
    RAISE EXCEPTION 'post-import structured record count mismatch';
 END IF;
END $guard$;
COMMIT;
SELECT 'resources='||count(*) FROM dp_resources
 WHERE collection_id='arvectum-market-pq-6-35kv';
SELECT 'records='||count(*) FROM dp_records WHERE resource_id IN
 (SELECT resource_id FROM dp_resources
  WHERE collection_id='arvectum-market-pq-6-35kv');
"""


def backup(directory: Path) -> None:
    if not directory.is_absolute() or not BACKUP.is_file():
        raise RuntimeError("official backup helper / absolute path required")
    p = subprocess.run(
        [str(BACKUP), "--container", CONTAINER, "--database", DATABASE,
         "--output-dir", str(directory)],
        capture_output=True, text=True, timeout=180,
    )
    if p.returncode or "SHA256=" not in p.stdout or "MANIFEST=" not in p.stdout:
        raise RuntimeError("backup failed, refusing database mutation")


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check-db", action="store_true")
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--approved-command", default=None)
    cli.add_argument("--backup-directory", type=Path, default=None)
    args = cli.parse_args()
    rows = stage()
    result = {"mode": "apply" if args.apply else "dry-run",
              "database": DATABASE, "collection": COLLECTION,
              "staged_records": len(rows), "existing_collections_touched": False,
              "search_index_or_embeddings_created": False}
    if args.check_db or args.apply:
        result["preflight"] = inspect_target()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not args.apply:
        return 0
    if args.approved_command != ACK or args.backup_directory is None:
        raise SystemExit("Owner must approve the exact target and command before writes")
    pre = result["preflight"]
    if pre["pq_resources"] not in (0, 71) or pre["pq_records"] not in (0, 71):
        raise SystemExit("Existing target contains unexpected partial data")
    backup(args.backup_directory)
    print(query(build_apply_sql(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
