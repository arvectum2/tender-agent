"""Read-only local analyzer for normalized market intelligence snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import analyze_market, render_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-bounded offline market report")
    parser.add_argument("--input", required=True, type=Path, help="Normalized JSON snapshot")
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--md-out", required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() in (args.json_out.resolve(), args.md_out.resolve()):
        parser.error("outputs must not overwrite the source snapshot")
    if args.json_out.resolve() == args.md_out.resolve():
        parser.error("JSON and Markdown destinations must be different")
    result = analyze_market(json.loads(args.input.read_text(encoding="utf-8")))
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    args.md_out.write_text(render_markdown(result), encoding="utf-8")


if __name__ == "__main__":
    main()
