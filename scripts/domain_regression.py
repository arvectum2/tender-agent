#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.modules.domain_regression.registry import (
    DEFAULT_MANIFEST,
    ManifestError,
    load_manifest,
    run_registered_cases,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and run the procurement domain regression registry.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--case-id", action="append", default=[])
    run.add_argument("--component", action="append", default=[])
    run.add_argument("--output", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "validate":
            manifest = load_manifest(args.manifest, root=ROOT)
            payload = {"schema_version": manifest["schema_version"], "case_count": len(manifest["cases"]), "status": "valid"}
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else f"valid: {payload['case_count']} cases")
            return 0
        report = run_registered_cases(
            args.manifest,
            root=ROOT,
            case_ids=set(args.case_id) or None,
            components=set(args.component) or None,
        )
        output = (ROOT / args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(output.relative_to(ROOT))
        return 0 if report["summary"]["failed"] == 0 else 1
    except ManifestError as exc:
        print(f"domain-regression manifest error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
