"""Read-only PQ v9 staging to Data Platform resource format; NO database writes."""
from __future__ import annotations
import json
import sys
from export_pq_data_platform import export_records
from materialize_pq_research_v9 import materialize


def main():
    records = export_records(materialize())
    if len(records) != 64:
        raise ValueError("64 resource staging count expected")
    for record in records:
        sys.stdout.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
