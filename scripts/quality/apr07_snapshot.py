#!/usr/bin/env python3
"""APR-07: consume existing evidence only; do not load/download models."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.modules.quality_slo.snapshot import (
    QualityEvidenceError,
    build_snapshot,
    include_bounded_analysis_latency,
)


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dp-result-dir", type=Path)
    parser.add_argument("--analysis-log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args(args)
    try:
        snapshot = build_snapshot(ROOT, opts.dp_result_dir)
        if opts.analysis_log is not None:
            snapshot = include_bounded_analysis_latency(snapshot, opts.analysis_log)
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        with opts.output.open("x", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
    except (QualityEvidenceError, FileExistsError, OSError) as exc:
        print(f"APR07_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "EXPLORATORY_UNREVIEWED_NOT_SLO_ACCEPTED",
                      "snapshot_sha256": snapshot["snapshot_sha256"],
                      "output": str(opts.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
