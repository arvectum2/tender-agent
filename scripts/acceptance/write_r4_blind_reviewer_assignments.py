"""Create empty reviewer assignments from existing source-only evaluator bundles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_blind_reviewer_assignment import (
    build_source_only_assignment,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluator-root", type=Path, required=True)
    args = parser.parse_args()
    bundles = sorted(args.evaluator_root.glob("*/evaluator_bundle.json"))
    if not bundles:
        raise ValueError("No pre-SUT source-only evaluator bundles available")
    for source in bundles:
        bundle = json.loads(source.read_text("utf8"))
        assignment = build_source_only_assignment(bundle)
        output = source.parent / "independent-reviewer-worksheet.md"
        output.write_text(assignment, encoding="utf8")
        print("SOURCE_ONLY_EXPERT_WORKSHEET_PREPARED", bundle["case_id"])
    print("INDEPENDENT_LEGAL_GOLD_SIGNED", 0)


if __name__ == "__main__":
    main()
