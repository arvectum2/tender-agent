"""Read-only MI-013 v12 Data Platform staging, no SQL or network writes."""
from __future__ import annotations
import json
import sys
from export_pq_data_platform import export_records
from materialize_pq_research_v12 import materialize


def main() -> int:
    records=export_records(materialize())
    if len(records)!=71:
        raise ValueError("v12 enriched corpus must retain 71 stable resources")
    if len({x["external_id"] for x in records})!=71:
        raise ValueError("duplicate ID after v12 enrichment")
    for item in records:
        sys.stdout.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
