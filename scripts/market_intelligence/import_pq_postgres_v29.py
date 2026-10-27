"""MI-013 v29: guarded incremental source-backed PostgreSQL import.

The canonical corpus contains 100 materialised procurement notice/lot records at v20,
one additional original notice at v23, and v21-v28 source-grade annotations.
The v29 Elga engineering project is NOT a procurement notice and is NOT imported.

Default is dry-run. --apply requires a verified pre-import pg_dump and explicit
owner ack; the transaction edits only tender-agent's PQ collection.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from export_pq_data_platform import export_records
from materialize_pq_research_v12 import materialize as materialize_v12
from materialize_pq_research_v20 import materialize as materialize_v20

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/market_intelligence/power_quality"
DB = "arvectum_data"
CONTAINER = "arvectum-postgres"
COLLECTION = "arvectum-market-pq-6-35kv"
SOURCE = "market_intelligence_procurement_research"
ACK = "MI013-101-V29-20261027"
BACKUP_HELPER = Path("/Volumes/ArvectumSSD/Arvectum/repos/data-platform/scripts/ops/backup-postgres.sh")
EVIDENCE = {
    "v21": ("primary_spec_protocol_enrichment_20261027.v21.json", "patches"),
    "v22": ("primary_competitor_award_enrichment_20261027.v22.json", "patches"),
    "v24": ("original_bsk_contractor_contract_20261027.v24.json", "patches"),
    "v25": ("original_nikitskaya_epc_protocol_boq_20261027.v25.json", "patches"),
    "v26": ("primary_stk_skrm_designer_competition_20261027.v26.json", "patches"),
    "v27": ("primary_filter_capacitors_and_ukrm_20261027.v27.json", "source_cases"),
    "v28": ("original_2027_condenser_mixed_voltage_bom_20261027.v28.json", "patches"),
}


def _json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def materialize_v29() -> dict:
    manifest = _json("verified_public_leads_20261027.v29.manifest.json")
    if manifest["total_active_rows"] != 101 or manifest["new_git_only_rows"] != 30:
        raise ValueError("MI-013 v29 expected manifest changed")
    base = materialize_v20()
    old = copy.deepcopy(base["records"])
    if len(old) != 100:
        raise ValueError("materialised v20 source changed")
    older_ids = [r["canonical_id"] for r in old]
    addition = _json("new_rosseti_ntc_components_framework_20261027.v23.json")
    if len(addition["records"]) != 1 or addition["append_only_new_records"] != 1:
        raise ValueError("v23 addition is not one original procurement")
    item = copy.deepcopy(addition["records"][0])
    if item["canonical_id"] != "223fz:32616355390:lot1" or item["canonical_id"] in older_ids:
        raise ValueError("v23 canonical ID unexpectedly overlaps pre-existing procurement")
    old.append(item)
    index = {r["canonical_id"]: r for r in old}
    if len(index) != 101:
        raise ValueError("v29 canonical IDs not unique")

    for version, (file_name, key) in EVIDENCE.items():
        doc = _json(file_name)
        patches = doc[key]
        if not isinstance(patches, list) or not patches:
            raise ValueError(f"{version}: original source patches not found")
        seen = set()
        for patch in patches:
            cid = patch.get("canonical_id") or patch.get("id")
            if cid not in index or cid in seen:
                raise ValueError(f"{version}: unknown or duplicate original ID {cid}")
            seen.add(cid)
            target = index[cid]
            target.setdefault("mi013_source_enrichments", {})[version] = {
                "source_file": file_name,
                "verified_original": copy.deepcopy(patch),
            }

    # Source v28 is an entire two-lot procurement. The earlier v28 patch
    # is anchored on lot 1, but its itemized XLSX affects interpretation of
    # BOTH lot 1 and lot 2; explicitly annotate the related lot without
    # changing its original legal notice/price or assigning the full NMC
    # to the 11.55kV item.
    mixed = "223fz:32616474682:lot1"
    sibling = "223fz:32616474682:lot2"
    if mixed not in index or sibling not in index:
        raise ValueError("expected two BESK legal lot keys missing")
    technical = index[mixed]["mi013_source_enrichments"]["v28"]
    index[sibling].setdefault("mi013_source_enrichments", {})["v28"] = {
        "source_file": technical["source_file"],
        "original_lot_reconciliation": {
            "lot_scope": "15 × 1.05kV LOW-voltage plus 1 × 11.55kV / 430kvar MEDIUM-voltage",
            "supplier_original_and_signed_contract": None,
            "single_medium_voltage_component_price": None,
            "whole_lot_is_not_medium_voltage_price": True,
            "technical_source": technical["verified_original"]["original_sources"][0],
        },
    }

    engineering = _json("primary_engineering_elga_2024_20261027.v29.json")
    if engineering["added_procurement_notices"] != 0 or any(
        x["id"] in index for x in engineering["projects"]
    ):
        raise ValueError("engineering-only demand mixed into legal procurement notice census")
    if any(x["canonical_id"] == "223fz:2024-mogocha-unverified:lot1" for x in old):
        raise ValueError("retracted Mogocha tender reintroduced")
    if len(old) != 101 or len(set(x["canonical_id"] for x in old)) != 101:
        raise ValueError("unexpected v29 notice total")
    return {
        **base,
        "data_version": "v29",
        "materialization_manifest": "verified_public_leads_20261027.v29.manifest.json",
        "records": old,
        "verification_summary": {
            "total_lot_level_records": 101,
            "production_structured_records_imported_before_apply": 71,
            "new_records_pending_import": 30,
            "named_original_protocol_company_occurrences": 28,
            "first_party_signed_contracts_known": 5,
            "one_engineering_stage_design_lead_not_imported": True,
            "market_population_complete": False,
        },
    }


def stage() -> list[dict]:
    ds = materialize_v29()
    rows = export_records(ds)
    old_ids = {x["canonical_id"] for x in materialize_v12()["records"]}
    all_ids = [x["external_id"] for x in rows]
    if len(rows) != 101 or len(set(all_ids)) != 101:
        raise ValueError("incorrect number of unique staged procurement records")
    if len(set(all_ids) & old_ids) != 71 or len(set(all_ids) - old_ids) != 30:
        raise ValueError("data v12 identity drift or incorrect number of additions")
    for row in rows:
        cid = row["external_id"]
        digest = hashlib.sha256(cid.encode("utf-8")).hexdigest()
        if row["resource_id"] != digest[:48]:
            raise ValueError("unstable database resource identity")
        if row["canonical_uri"] != f"urn:arvectum:pq:procurement:{digest}":
            raise ValueError("canonical URI drift")
        if row["collection_id"] != COLLECTION or row["source_type"] != SOURCE:
            raise ValueError("unexpected tenant/collection/source")
        if row["status"] != "staged_unreviewed":
            raise ValueError("tried prematurely approving research")
        if not row["metadata"]["research_not_market_population"]:
            raise ValueError("market population assumption unsafe")
        evidence = row["metadata"]["source_urls"]
        if not evidence or any(not x.startswith("https://") for x in evidence):
            raise ValueError("source-less row in staged corpus")
        row["metadata"]["data_version"] = "v29"
        row["metadata"]["mi013_import_batch"] = "v29-20261027"
        row["metadata"]["source_evidence_versions"] = sorted(
            row["source_record"].get("mi013_source_enrichments", {}).keys()
        )
    return rows


def query(sql: str, timeout: int = 120) -> str:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker executable missing")
    p = subprocess.run(
        [docker, "exec", "-i", CONTAINER, "psql", "-X", "-q", "-A", "-t",
         "-v", "ON_ERROR_STOP=1", "-U", "arvectum", "-d", DB],
        input=sql, capture_output=True, text=True, timeout=timeout,
    )
    if p.returncode:
        raise RuntimeError("PostgreSQL command failed: " + p.stderr[-700:])
    return p.stdout.strip()


def snapshot() -> dict:
    sql = r"""
BEGIN READ ONLY;
SELECT jsonb_build_object(
  'database',current_database(),
  'owner',(SELECT owner FROM dp_collections WHERE collection_id='arvectum-market-pq-6-35kv'),
  'resources',(SELECT count(*) FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv'),
  'records',(SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv')),
  'unique_ids',(SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv'),
  'not_unreviewed',(SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.collection_id='arvectum-market-pq-6-35kv' AND d.review_status<>'unreviewed'),
  'other_resources',(SELECT count(*) FROM dp_resources WHERE collection_id<>'arvectum-market-pq-6-35kv'),
  'other_records',(SELECT count(*) FROM dp_records WHERE resource_id NOT IN (SELECT resource_id FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv')),
  'all_documents',(SELECT count(*) FROM dp_documents),
  'source_version_29',(SELECT count(*) FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv' AND metadata->>'data_version'='v29')
)::text;
COMMIT;
"""
    result = query(sql)
    data = json.loads(result)
    if data["database"] != DB or data["owner"] != "tender-agent":
        raise RuntimeError("target database/collection owner mismatch")
    return data


def stage_db_check(rows: list[dict]) -> dict:
    # Confirm every one of 71 original resource IDs is present and owned by
    # this source, before any insert or update.
    first71 = {x["resource_id"] for x in export_records(materialize_v12())}
    ids = ",".join("'" + h + "'" for h in sorted(first71))
    sql = f"""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'original_match',(SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}' AND source_type='{SOURCE}' AND resource_id IN ({ids})),
 'other_owned',(SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}' AND (source_type<>'{SOURCE}' OR status<>'staged_unreviewed')),
 'foreign_record',(SELECT count(*) FROM dp_records r JOIN dp_resources s USING(resource_id) WHERE s.collection_id='{COLLECTION}' AND r.record_type<>'pq_procurement_notice_lot'),
 'staged_existing',(SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}' AND external_id IN ({",".join("'" + x["external_id"].replace("'", "''") + "'" for x in rows)}))
)::text;
COMMIT;"""
    out = json.loads(query(sql))
    if out != {
        "original_match": 71, "other_owned": 0,
        "foreign_record": 0, "staged_existing": 71,
    }:
        raise RuntimeError(f"unsafe SQL preflight: {out}")
    return out


def make_sql(rows: list[dict], other_before: dict) -> str:
    if len(rows) != 101:
        raise ValueError("incorrect SQL payload size")
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    hexdata = payload.encode("utf-8").hex()
    return f"""
BEGIN;
SET LOCAL statement_timeout='120s';
SET LOCAL lock_timeout='10s';
SELECT pg_advisory_xact_lock(hashtext('mi013-pq-v29-101'));
DO $guard$
BEGIN
 IF current_database()<>'{DB}' OR
 (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent' THEN
   RAISE EXCEPTION 'wrong target tenant';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>71 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN
    (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>71 THEN
    RAISE EXCEPTION 'unexpected changed initial PQ count';
 END IF;
END $guard$;
CREATE TEMP TABLE mi013_stage(item jsonb NOT NULL) ON COMMIT DROP;
INSERT INTO mi013_stage SELECT value FROM jsonb_array_elements(
 convert_from(decode('{hexdata}','hex'),'UTF8')::jsonb);
DO $guard$
BEGIN
 IF (SELECT count(*) FROM mi013_stage)<>101 OR
    (SELECT count(DISTINCT item->>'resource_id') FROM mi013_stage)<>101 OR
    (SELECT count(DISTINCT item->>'external_id') FROM mi013_stage)<>101 THEN
   RAISE EXCEPTION 'staged ids/count invalid';
 END IF;
 IF (SELECT count(*) FROM mi013_stage a JOIN dp_resources r ON r.resource_id=a.item->>'resource_id'
     WHERE r.collection_id='{COLLECTION}' AND r.source_type='{SOURCE}' AND r.canonical_uri=a.item->>'canonical_uri')<>71 THEN
   RAISE EXCEPTION 'old 71 identity mismatch';
 END IF;
 IF EXISTS(SELECT 1 FROM mi013_stage a JOIN dp_resources r ON r.resource_id=a.item->>'resource_id'
     WHERE r.collection_id<>'{COLLECTION}' OR r.source_type<>'{SOURCE}' OR r.canonical_uri<>a.item->>'canonical_uri') THEN
   RAISE EXCEPTION 'cross-tenant resource collision';
 END IF;
 IF EXISTS(SELECT 1 FROM mi013_stage a JOIN dp_records r ON r.record_id='pq:'||(a.item->>'resource_id')
     WHERE r.resource_id<>a.item->>'resource_id' OR r.record_type<>'pq_procurement_notice_lot') THEN
   RAISE EXCEPTION 'cross-tenant record collision';
 END IF;
END $guard$;
INSERT INTO dp_resources
(resource_id,collection_id,source_type,canonical_uri,external_id,content_hash,status,metadata,
 refresh_policy,first_seen_at,last_seen_at,created_at,updated_at)
SELECT item->>'resource_id','{COLLECTION}','{SOURCE}',item->>'canonical_uri',
 item->>'external_id',item->>'content_hash','staged_unreviewed',item->'metadata',
 '{{}}'::jsonb,now(),now(),now(),now() FROM mi013_stage
ON CONFLICT (resource_id) DO UPDATE SET
 content_hash=EXCLUDED.content_hash,
 metadata=dp_resources.metadata||EXCLUDED.metadata,
 last_seen_at=now(),updated_at=now()
WHERE dp_resources.content_hash IS DISTINCT FROM EXCLUDED.content_hash
 OR NOT(dp_resources.metadata @> EXCLUDED.metadata);
INSERT INTO dp_records
(record_id,resource_id,record_type,data,revision,review_status,metadata,created_at,updated_at)
SELECT 'pq:'||(item->>'resource_id'),item->>'resource_id','pq_procurement_notice_lot',
 item->'source_record',1,'unreviewed',jsonb_build_object(
 'source_content_hash',item->>'content_hash',
 'source_evidence_urls',item->'metadata'->'source_urls',
 'research_version','v29'),now(),now() FROM mi013_stage
ON CONFLICT (record_id) DO UPDATE SET
 data=EXCLUDED.data,
 metadata=dp_records.metadata||EXCLUDED.metadata,
 revision=dp_records.revision+1,updated_at=now()
WHERE dp_records.data IS DISTINCT FROM EXCLUDED.data
 OR NOT(dp_records.metadata @> EXCLUDED.metadata);
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101 OR
    (SELECT count(*) FROM dp_records WHERE resource_id IN
       (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>101 OR
    (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101 OR
    (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}' AND metadata->>'data_version'='v29')<>101 THEN
   RAISE EXCEPTION 'v29 post-write integrity mismatch, rolling back';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{other_before["other_resources"]} OR
    (SELECT count(*) FROM dp_records WHERE resource_id NOT IN
       (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>{other_before["other_records"]} OR
    (SELECT count(*) FROM dp_documents)<>{other_before["all_documents"]} THEN
   RAISE EXCEPTION 'other Data Platform collections changed during import';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V29_RESOURCES='||count(*) FROM dp_resources WHERE collection_id='{COLLECTION}';
SELECT 'MI013_V29_RECORDS='||count(*) FROM dp_records WHERE resource_id IN
(SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}');
"""


def backup(dest: Path) -> dict:
    if not dest.is_absolute() or not dest.is_dir() or not BACKUP_HELPER.is_file():
        raise RuntimeError("original backup helper and existing absolute destination required")
    p = subprocess.run([
        str(BACKUP_HELPER), "--container", CONTAINER, "--database", DB,
        "--output-dir", str(dest)
    ], capture_output=True, text=True, timeout=180)
    if p.returncode:
        raise RuntimeError("failed official PostgreSQL backup; no SQL performed: " + p.stderr[-500:])
    fields = {}
    for line in p.stdout.splitlines():
        key, sep, val = line.partition("=")
        if sep and key in {"BACKUP", "SHA256", "BYTES", "MANIFEST"}:
            if key in fields:
                raise RuntimeError("duplicate backup field")
            fields[key] = val
    if set(fields) != {"BACKUP", "SHA256", "BYTES", "MANIFEST"}:
        raise RuntimeError("backup file fields missing")
    d = Path(fields["BACKUP"]).resolve()
    m = Path(fields["MANIFEST"]).resolve()
    if not d.is_relative_to(dest.resolve()) or not m.is_relative_to(dest.resolve()):
        raise RuntimeError("backup outside expected dir")
    if not d.is_file() or not m.is_file():
        raise RuntimeError("backup file missing")
    size = d.stat().st_size
    digest = hashlib.file_digest(d.open("rb"), "sha256").hexdigest()
    doc = json.loads(m.read_text(encoding="utf-8"))
    ck = Path(str(d) + ".sha256")
    if (
        size <= 0 or size != int(fields["BYTES"]) or digest != fields["SHA256"]
        or ck.read_text(encoding="utf-8").strip() != digest
        or doc.get("sha256") != digest or doc.get("database") != DB
        or doc.get("container") != CONTAINER or doc.get("bytes") != size
    ):
        raise RuntimeError("backup checksum / manifest verification failed")
    return {"file": d.name, "directory": str(d.parent), "bytes": size, "sha256": digest}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check-db", action="store_true")
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--approved-command", default=None)
    cli.add_argument("--backup-directory", type=Path, default=None)
    args = cli.parse_args()
    rows = stage()
    report = {
        "stage":"v29","rows":len(rows),"unique_procurement_keys":len({r["external_id"] for r in rows}),
        "new_expected":30,"former_expected":71,
        "stage_content_sha256":hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True, separators=(",",":")).encode("utf-8")).hexdigest(),
        "engineering_project_only_not_imported":True,
    }
    if args.check_db or args.apply:
        report["db_before"] = snapshot()
        if report["db_before"]["resources"] != 71 or report["db_before"]["records"] != 71:
            raise RuntimeError("refuse unexpected DB state")
        report["sql_stage"] = stage_db_check(rows)
    print(json.dumps(report,ensure_ascii=False,sort_keys=True),flush=True)
    if not args.apply:
        return 0
    if args.approved_command != ACK or args.backup_directory is None:
        raise SystemExit("explicit owner-approved per-command token and backup dir required")
    full_backup = backup(args.backup_directory)
    print(json.dumps({"verified_pre_import_backup":full_backup},ensure_ascii=False),flush=True)
    response = query(make_sql(rows,report["db_before"]),timeout=160)
    if "MI013_V29_RESOURCES=101" not in response or "MI013_V29_RECORDS=101" not in response:
        raise RuntimeError("SQL terminal post-write count not reported; verify DB independently")
    after = snapshot()
    expected = {"resources":101,"records":101,"unique_ids":101,"source_version_29":101,"not_unreviewed":0}
    if any(after[k]!=v for k,v in expected.items()):
        raise RuntimeError(f"v29 read-back mismatch {after}")
    if any(after[k]!=report["db_before"][k] for k in ["other_resources","other_records","all_documents"]):
        raise RuntimeError("unrelated Data Platform content count changed")
    print(json.dumps({"result":"PASS","db_after":after,"backup":full_backup},ensure_ascii=False,sort_keys=True),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
