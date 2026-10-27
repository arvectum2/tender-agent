"""Read-only acceptance audit for MI-013 Power Quality Data Platform collection.

Always executes a PostgreSQL READ ONLY transaction; never creates resources,
contracts, schemas or embeddings. By default prints an independently measured
snapshot, --expect-import asserts all 71 planned resource/record pairs exist.
"""
from __future__ import annotations

import argparse
import json

from import_pq_postgres_v12 import COLLECTION, DATABASE, query

EXPECTED = 71


def build_snapshot_query() -> str:
    return """
BEGIN READ ONLY;
SELECT jsonb_build_object(
  'database', current_database(),
  'collection_id', 'arvectum-market-pq-6-35kv',
  'collection_count',
     (SELECT count(*) FROM dp_collections
      WHERE collection_id='arvectum-market-pq-6-35kv'),
  'pq_resources',
     (SELECT count(*) FROM dp_resources
      WHERE collection_id='arvectum-market-pq-6-35kv'),
  'pq_records',
     (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
      WHERE r.collection_id='arvectum-market-pq-6-35kv'),
  'unique_canonical_ids',
     (SELECT count(DISTINCT r.external_id) FROM dp_resources r
      WHERE r.collection_id='arvectum-market-pq-6-35kv'),
  'unreviewed_records',
     (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
      WHERE r.collection_id='arvectum-market-pq-6-35kv'
        AND d.review_status='unreviewed'),
  'missing_source_urls',
     (SELECT count(*) FROM dp_resources r
      WHERE r.collection_id='arvectum-market-pq-6-35kv'
        AND coalesce(jsonb_array_length(
            CASE WHEN jsonb_typeof(r.metadata->'source_urls')='array'
              THEN r.metadata->'source_urls' ELSE '[]'::jsonb END), 0)=0),
  'joint_besk_lot_count',
     (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
      WHERE r.collection_id='arvectum-market-pq-6-35kv'
        AND d.data->>'procedure_id'='32616474682'),
  'joint_besk_distinct_lots',
     (SELECT count(DISTINCT d.data->>'lot_number')
      FROM dp_records d JOIN dp_resources r USING(resource_id)
      WHERE r.collection_id='arvectum-market-pq-6-35kv'
        AND d.data->>'procedure_id'='32616474682'),
  'original_10kv_mpu_evidence',
     (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
      WHERE r.collection_id='arvectum-market-pq-6-35kv'
        AND d.data->>'procedure_id'='32616435269'
        AND d.data->>'boq_mpu_10kv_net_rub'='335351974.38'
        AND d.data->>'boq_bsk_110kv_net_rub'='33723435.46'
        AND d.data->>'nmc_gross_rub'='452016000.01'
        AND d.data->>'source_original_docs_verified'='true'),
  'other_collections',
     (SELECT count(*) FROM dp_collections
      WHERE collection_id<>'arvectum-market-pq-6-35kv'),
  'other_resources',
     (SELECT count(*) FROM dp_resources
      WHERE collection_id<>'arvectum-market-pq-6-35kv'),
  'all_documents', (SELECT count(*) FROM dp_documents)
)::text;
COMMIT;
"""


def snapshot() -> dict:
    lines = [
        x.strip() for x in query(build_snapshot_query()).splitlines()
        if x.strip() and x.strip() not in {"BEGIN", "COMMIT"}
    ]
    if len(lines) != 1:
        raise RuntimeError("read-only PostgreSQL audit did not return one JSON snapshot")
    doc = json.loads(lines[0])
    if doc["database"] != DATABASE or doc["collection_id"] != COLLECTION:
        raise RuntimeError("audit pointed to unexpected Data Platform database/collection")
    return doc


def verify_imported(data: dict) -> None:
    expected = {
        "collection_count": 1,
        "pq_resources": EXPECTED,
        "pq_records": EXPECTED,
        "unique_canonical_ids": EXPECTED,
        "unreviewed_records": EXPECTED,
        "missing_source_urls": 0,
        "joint_besk_lot_count": 2,
        "joint_besk_distinct_lots": 2,
        "original_10kv_mpu_evidence": 1,
    }
    for field, desired in expected.items():
        if data.get(field) != desired:
            raise ValueError(f"acceptance failed: {field}={data.get(field)} expected {desired}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-import", action="store_true",
                        help="fail unless 71 records exist and key details match")
    args = parser.parse_args()
    result = snapshot()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.expect_import:
        verify_imported(result)
        print("MI013 import read-back acceptance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
