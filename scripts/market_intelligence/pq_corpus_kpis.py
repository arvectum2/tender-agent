"""Read-only, reproducible UNIQUE procurement KPIs for the PQ research corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import psql


def collect() -> dict:
    # Treat legal notice/lot keys and signed-equipment sales as distinct
    # dimensions. Never calculate TAM from mixed EPC or unreviewed notices.
    sql = """
BEGIN READ ONLY;
SELECT jsonb_build_object(
 'database',current_database(),
 'collection','arvectum-market-pq-6-35kv',
 'unique_lots',count(distinct r.external_id),
 'lot_rows',count(*),
 'distinct_procedure_tokens',count(distinct split_part(r.external_id,':',2)),
 'eis_223_lots',count(*) FILTER
   (WHERE r.external_id ~ '^223fz:[0-9]{11}:lot[0-9]+$'),
 'eis_223_notices',count(distinct split_part(r.external_id,':',2)) FILTER
   (WHERE r.external_id ~ '^223fz:[0-9]{11}:lot[0-9]+$'),
 'other_lot_cards',count(*) FILTER
   (WHERE r.external_id !~ '^223fz:[0-9]{11}:lot[0-9]+$'),
 'unreviewed_rows',count(*) FILTER (WHERE d.review_status='unreviewed'),
 'rows_with_original_shas_in_metadata',count(*) FILTER
   (WHERE jsonb_typeof(r.metadata->'source_original_sha256')='array'),
 'rows_marked_research_not_market_population',count(*) FILTER
   (WHERE r.metadata->>'research_not_market_population'='true'),
 'registered_signed_supplier_ids_in_resource_metadata',count(*) FILTER
   (WHERE r.metadata->>'winning_supplier_only_if_verified' IS NOT NULL)

)::text
FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='arvectum-market-pq-6-35kv';
COMMIT;"""
    result = psql(sql)
    lines = [s for s in result.splitlines() if s.startswith("{")]
    if len(lines) != 1:
        raise RuntimeError("Missing structured PostgreSQL result")
    obj = json.loads(lines[0])
    if obj["database"] != "arvectum_data" or obj["lot_rows"] != obj["unique_lots"]:
        raise RuntimeError("Wrong database or duplicate lot IDs")
    if obj["unreviewed_rows"] > obj["lot_rows"]:
        raise RuntimeError("Impossible review-state count")
    return {
        "schema_version": "pq-live-corpus-kpi/1",
        "scope": "research_corpus_not_national_market_population",
        "counts": obj,
        "definitions": {
            "unique_lots": "One canonical notice:lot ID per legal or commercial request; may be non-binding",
            "distinct_procedure_tokens": "Count of distinct second-colon ID parts; not the same as unique projects or executed contracts",
            "eis_223_notices": "Distinct 11-digit 223-FZ identifiers, not contracts signed",
            "other_lot_cards": "Commercial and nonstandard research lots; may include unverified technical voltage",
            "original_sha_metadata": "Only SHA in dp_resources.metadata; excludes historical source verification stored elsewhere",
            "verified_equipment_sales_rub": "Not computed without independent signed supplier, item price and execution records",
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--save", type=Path)
    args = p.parse_args()
    data = collect()
    if args.save:
        if args.save.is_symlink():
            raise ValueError("Output path is symlink")
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(data,ensure_ascii=False))


if __name__ == "__main__":
    main()
