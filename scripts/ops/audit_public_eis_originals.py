"""Read-only public EIS attachment receipts to a new isolated directory.

Example: python scripts/ops/audit_public_eis_originals.py 0372200172326000015 zk20 --output /tmp/eis-original-check
Never modifies Tender Agent runs, Data Platform records, or EIS.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.eis_public_original_receipts import (
    fetch_public_original_receipts,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry_number")
    parser.add_argument("notice_type")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest, sources = fetch_public_original_receipts(
        reg_number=args.registry_number, notice_type=args.notice_type
    )
    directory = args.output.expanduser()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for uid, binary in sources.items():
        (directory / f"{uid}.bin").write_bytes(binary)
    (directory / "receipts.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "procurement_number": manifest["procurement_number"],
                "file_count": len(sources),
                "total_bytes": manifest["total_bytes"],
                "page_edition_ui_label": manifest["page_edition_ui_label"],
                "independent_eis_revision_verified": False,
                "data_platform_identity_verified": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
