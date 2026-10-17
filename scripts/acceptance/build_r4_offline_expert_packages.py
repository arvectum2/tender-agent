"""Export private real-original packages only; never contact an external expert."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_offline_expert_package import (
    write_source_only_reviewer_package,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evaluator-root", type=Path, required=True)
    ap.add_argument("--original-source-root", type=Path, required=True)
    ap.add_argument("--private-output-root", type=Path, required=True)
    args = ap.parse_args()
    dirs = sorted(p.parent for p in args.evaluator_root.glob("*/evaluator_bundle.json"))
    if not dirs:
        raise ValueError("No source-only evaluator bundles to prepare")
    if args.private_output_root.exists() and any(args.private_output_root.iterdir()):
        raise ValueError("No overwrite of preexisting reviewer delivery receipts")
    args.private_output_root.mkdir(parents=True, exist_ok=True)
    results = []
    for directory in dirs:
        results.append(write_source_only_reviewer_package(
            reviewer_bundle_dir=directory,
            original_source_root=args.original_source_root,
            private_output=args.private_output_root / (directory.name + ".zip"),
        ))
    (args.private_output_root / "private-offline-handoff-receipt.json").write_text(
        json.dumps({
            "case_count": len(results), "source_only": True,
            "reviewer_external_contact_done": False,
            "expert_gold_received": 0,
            "sut_run_authorized": False,
            "packages": results,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf8",
    )
    print("SOURCE_ONLY_OFFLINE_HUMAN_PACKAGES",len(results),"GOLD",0,"EXTERNAL_CONTACT",False)


if __name__ == "__main__":
    main()
