"""Read-only v10 Data Platform staged JSONL exporter (68 canonical procedure IDs)."""
from __future__ import annotations

import json
import sys
from export_pq_data_platform import export_records
from materialize_pq_research_v10 import materialize


def main() -> int:
    payload = export_records(materialize())
    if len(payload) != 68:
        raise ValueError("v10 staging must emit exactly 68 procurement resources")
    if len({r["external_id"] for r in payload}) != 68:
        raise ValueError("duplicate 68-item canonical ID")
    for item in payload:
        sys.stdout.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
