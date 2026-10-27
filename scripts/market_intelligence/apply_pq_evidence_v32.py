"""MI013 v32: guarded and backup-verified two-case original source enrichment.

Use read-only --check-db before --apply. Modifies only two already-present
procurement JSONB records: Sibsteklo original customer-owned 6kV UKRM TЗ and
2024 Turan failed EPC original EIS protocol. Zero new notices or signed awards.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

from import_pq_postgres_v29 import (
    COLLECTION, SOURCE, DATA, backup, query, snapshot,
)

FILENAME = "primary_sibsteklo_turan_docs_20261027.v32.json"
ACK = "MI013-V32-TWO-20261027"
TARGETS = {"commercial:306-644:lot35", "223fz:32413708738:lot1"}


def evidence():
    raw = json.loads((DATA / FILENAME).read_text(encoding="utf-8"))
    patches = raw["source_patches"]
    ids = {p["canonical_id"] for p in patches}
    if ids != TARGETS or len(patches) != 2 or raw["new_procurement_notices"] != 0:
        raise ValueError("expected two existing original-source updates only")
    original_urls = []
    for p in patches:
        if not p["evidence"] or any(
            not e["url"].startswith("https://") or not
            (e.get("sha256") and len(e["sha256"]) == 64 or e["tier"].startswith("first_party_"))
            for e in p["evidence"]
        ):
            raise ValueError("inadequate original source provenance")
        original_urls.extend(e["url"] for e in p["evidence"])
    turan = next(p for p in patches if p["canonical_id"].startswith("223fz:"))
    sib = next(p for p in patches if p["canonical_id"].startswith("commercial:"))
    if (turan["original_admitted_bids"] != 0 or turan["original_rejected_bids"] != 2
        or turan["winner"] is not None or turan["original_registered_signed_contract_verified"]
        or sib["original_buyers_device_provided"] is not True
        or sib["hardware_new_sale_count"] != 0 or sib["original_signed_contract_verified"]
        or sib["original_technical"]["devices_to_install"] != 2
        or sib["original_technical"]["each_voltage_kv"] != 6
        or sib["original_technical"]["each_power_kvar"] != 900):
        raise ValueError("unexpected signed contract or hardware classification")
    return {p["canonical_id"]: p for p in patches}


def get_existing(ids: set[str]) -> dict:
    # literal known fixed canonical IDs; quote-safe by encoding ids as quoted literals
    values = ",".join("'" + v.replace("'", "''") + "'" for v in sorted(ids))
    sql = f"""BEGIN READ ONLY;
SELECT coalesce(jsonb_agg(jsonb_build_object(
 'resource_id',r.resource_id, 'external_id',r.external_id,
 'canonical_uri',r.canonical_uri, 'source_type',r.source_type,
 'status',r.status, 'collection_id',r.collection_id,
 'content_hash',r.content_hash, 'resource_metadata',r.metadata,
 'record_type',d.record_type, 'review_status',d.review_status,
 'data',d.data, 'record_metadata',d.metadata
 )), '[]'::jsonb)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COLLECTION}' AND r.external_id IN ({values});
COMMIT;"""
    fetched = json.loads(query(sql))
    found = {x["external_id"]: x for x in fetched}
    if set(found) != ids:
        raise RuntimeError(f"required existing resources missing: {set(ids)-set(found)}")
    for cid,x in found.items():
        if (x["collection_id"] != COLLECTION or x["source_type"] != SOURCE
            or x["status"] != "staged_unreviewed"
            or x["record_type"] != "pq_procurement_notice_lot"
            or x["review_status"] != "unreviewed"
            or x["resource_metadata"].get("data_version") not in ("v29", "v32")):
            raise RuntimeError(f"refuse mutable original provenance: {cid}")
    return found


def plan(patches: dict, fetched: dict) -> list[dict]:
    result = []
    for cid in sorted(patches):
        old = fetched[cid]
        data = copy.deepcopy(old["data"])
        p = patches[cid]
        evidence_versions = data.setdefault("mi013_source_enrichments", {})
        if "v32" in evidence_versions:
            previous = evidence_versions["v32"]["verified_original"]
            if previous != p:
                raise ValueError("already applied different v32 source")
            computed = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                                  separators=(",", ":")).encode("utf-8")).hexdigest()
            if computed != old["content_hash"]:
                raise RuntimeError(f"{cid}: earlier v32 content hash differs")
            result.append({"id":cid, "already":True})
            continue
        if old["resource_metadata"].get("data_version") != "v29":
            raise RuntimeError("new source update must not silently override later versions")
        evidence_versions["v32"] = {"source_file":FILENAME,"verified_original":p}
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        meta = copy.deepcopy(old["resource_metadata"])
        urls = list(dict.fromkeys(meta.get("source_urls", []) + [v["url"] for v in p["evidence"]]))
        meta.update({
            "source_urls":urls,
            "source_evidence_versions":sorted(evidence_versions),
            "research_last_primary_enrichment":"v32",
            "mi013_import_batch":"v32-20261027",
            "data_version":"v32",
        })
        record_meta = copy.deepcopy(old["record_metadata"])
        record_meta.update({
            "source_content_hash":digest,
            "source_evidence_urls":urls,
            "research_version":"v32"
        })
        result.append({
            "id":cid, "resource_id":old["resource_id"],
            "old_hash":old["content_hash"],"new_hash":digest,
            "canonical_uri":old["canonical_uri"],
            "data":data,"metadata":meta,"record_metadata":record_meta,
        })
    return result


def sql_for(rows: list[dict], before: dict) -> str:
    if len(rows) != 2 or any(r.get("already") for r in rows):
        raise ValueError("transaction requires two pending changes")
    payload = json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode().hex()
    return f"""
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
SELECT pg_advisory_xact_lock(hashtext('mi013-pq-v32-two-primary-sources'));
CREATE TEMP TABLE mi013_v32 (item jsonb NOT NULL) ON COMMIT DROP;
INSERT INTO mi013_v32 SELECT value FROM jsonb_array_elements(
convert_from(decode('{payload}','hex'),'UTF8')::jsonb);
DO $guard$
BEGIN
 IF current_database()<>'arvectum_data'
 OR (SELECT owner FROM dp_collections WHERE collection_id='{COLLECTION}')<>'tender-agent'
 OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101
 OR (SELECT count(*) FROM dp_records WHERE resource_id IN (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>101 THEN
   RAISE EXCEPTION 'unexpected database scope or corpus cardinality';
 END IF;
 IF (SELECT count(*) FROM mi013_v32)<>2 OR
    (SELECT count(DISTINCT item->>'id') FROM mi013_v32)<>2 THEN
    RAISE EXCEPTION 'wrong number of staged cases';
 END IF;
 IF (SELECT count(*) FROM mi013_v32 s
   JOIN dp_resources r ON r.resource_id=s.item->>'resource_id'
   JOIN dp_records d ON d.resource_id=r.resource_id
   WHERE r.collection_id='{COLLECTION}' AND r.source_type='{SOURCE}'
    AND r.external_id=s.item->>'id' AND r.canonical_uri=s.item->>'canonical_uri'
    AND r.content_hash=s.item->>'old_hash'
    AND r.status='staged_unreviewed' AND d.review_status='unreviewed'
    AND d.record_type='pq_procurement_notice_lot'
    AND NOT COALESCE(d.data->'mi013_source_enrichments'?'v32',false))<>2 THEN
   RAISE EXCEPTION 'existing source precondition mismatch';
 END IF;
END $guard$;
UPDATE dp_resources r SET
 content_hash=s.item->>'new_hash',
 metadata=s.item->'metadata',
 last_seen_at=now(),
 updated_at=now()
FROM mi013_v32 s WHERE r.resource_id=s.item->>'resource_id';
UPDATE dp_records d SET
 data=s.item->'data',
 metadata=s.item->'record_metadata',
 revision=revision+1, updated_at=now()
FROM mi013_v32 s WHERE d.resource_id=s.item->>'resource_id';
DO $guard$
BEGIN
 IF (SELECT count(*) FROM dp_resources WHERE collection_id='{COLLECTION}')<>101
    OR (SELECT count(*) FROM dp_records WHERE resource_id IN
        (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>101
    OR (SELECT count(*) FROM mi013_v32 s JOIN dp_resources r
        ON r.resource_id=s.item->>'resource_id'
        JOIN dp_records d USING(resource_id)
        WHERE r.content_hash=s.item->>'new_hash'
          AND d.data->'mi013_source_enrichments'?'v32')<>2 THEN
    RAISE EXCEPTION 'v32 source postwrite integrity mismatch';
 END IF;
 IF (SELECT count(*) FROM dp_resources WHERE collection_id<>'{COLLECTION}')<>{before['other_resources']}
   OR (SELECT count(*) FROM dp_documents)<>{before['all_documents']}
   OR (SELECT count(*) FROM dp_records WHERE resource_id NOT IN
        (SELECT resource_id FROM dp_resources WHERE collection_id='{COLLECTION}'))<>{before['other_records']} THEN
   RAISE EXCEPTION 'other Data Platform entities changed';
 END IF;
END $guard$;
COMMIT;
SELECT 'MI013_V32_ROWS='||count(*)
FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COLLECTION}' AND d.data->'mi013_source_enrichments'?'v32';
"""


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-db",action="store_true")
    p.add_argument("--apply",action="store_true")
    p.add_argument("--approved-command")
    p.add_argument("--backup-directory",type=Path)
    a=p.parse_args()
    patches=evidence()
    before=snapshot()
    if before["resources"]!=101 or before["records"]!=101:
        raise RuntimeError("current corpus cardinality not 101")
    items=plan(patches,get_existing(set(patches)))
    done=sum(bool(x.get("already")) for x in items)
    report={"stage":"v32","expected_existing_notice_count":101,"original_cases":list(sorted(patches)),
            "new_notices":0,"already_enriched":done,"pending":2-done}
    print(json.dumps(report,ensure_ascii=False,sort_keys=True),flush=True)
    if not a.apply:
        return 0
    if done==2:
        print("MI013 v32 already fully applied. No mutation.",flush=True)
        return 0
    if done or a.approved_command!=ACK or a.backup_directory is None:
        raise RuntimeError("partial state / missing authorized command; transaction refused")
    proof=backup(a.backup_directory)
    print(json.dumps({"backup_verified":proof},ensure_ascii=False),flush=True)
    out=query(sql_for(items,before),timeout=155)
    if "MI013_V32_ROWS=2" not in out:
        raise RuntimeError("commit receipt missing, inspect DB")
    after=snapshot()
    final=plan(patches,get_existing(set(patches)))
    if (after["resources"]!=101 or after["records"]!=101
        or after["other_resources"]!=before["other_resources"]
        or after["all_documents"]!=before["all_documents"]
        or not all(x.get("already") for x in final)):
        raise RuntimeError("independent readback mismatch")
    print(json.dumps({"result":"PASS","backed_up":proof,"db_after":after,
                      "row_hashes":{x["id"]:x.get("new_hash") or get_existing(set(patches))[x["id"]]["content_hash"] for x in items}},
                     ensure_ascii=False,sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
