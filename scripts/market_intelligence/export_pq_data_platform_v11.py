"""Read-only PQ market intelligence v11 staging: 71 lot-aware records."""
from __future__ import annotations
import json
import sys
from export_pq_data_platform import export_records
from materialize_pq_research_v11 import materialize

def main():
    payload = export_records(materialize())
    if len(payload) != 71:
        raise ValueError("v11 exporter must emit 71 canonical lot-level resources")
    for row in payload:
        sys.stdout.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
