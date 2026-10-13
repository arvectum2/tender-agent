"""Read-only structural duplicate-function audit for Tender Agent/Data Platform.

Exact AST-body equality can indicate redundant implementations but is NOT
authority to delete them: frozen/backward-compatible adapters are deliberate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _iter_files(root: Path) -> list[Path]:
    return sorted(
        file for file in root.rglob("*.py")
        if ".venv" not in file.parts and "__pycache__" not in file.parts
    )


def function_fingerprints(root: Path, *, label: str, min_lines: int = 12) -> list[dict[str, Any]]:
    fingerprints = []
    for path in _iter_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lines = (node.end_lineno or node.lineno) - node.lineno + 1
            if lines < min_lines:
                continue
            # Ignore docstring text when grouping logic: commentary is not
            # runtime code and shouldn't change the body fingerprint.
            body = list(node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]
            normalized = ast.dump(
                ast.Module(body=body, type_ignores=[]),
                annotate_fields=True,
                include_attributes=False,
            )
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            fingerprints.append({
                "repo": label,
                "file": str(path.relative_to(root)),
                "function": node.name,
                "lines": lines,
                "fingerprint": fingerprint[:16],
            })
    return fingerprints


def duplicate_groups(*roots: tuple[str, Path], min_lines: int = 12) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for label, root in roots:
        for row in function_fingerprints(root, label=label, min_lines=min_lines):
            grouped[row["fingerprint"]].append(row)
    result = []
    for fingerprint, rows in grouped.items():
        distinct = {(row["repo"], row["file"], row["function"]) for row in rows}
        if len(distinct) < 2:
            continue
        result.append({
            "fingerprint": fingerprint,
            "max_lines": max(row["lines"] for row in rows),
            "occurrences": rows,
            "cross_repo": len({row["repo"] for row in rows}) > 1,
        })
    return sorted(result, key=lambda group: (-group["max_lines"], group["fingerprint"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tender-agent-src", type=Path, default=ROOT / "src")
    parser.add_argument("--data-platform-src", type=Path)
    parser.add_argument("--min-lines", type=int, default=12)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    roots = [("tender-agent", args.tender_agent_src)]
    if args.data_platform_src:
        roots.append(("data-platform", args.data_platform_src))
    groups = duplicate_groups(*roots, min_lines=args.min_lines)
    print(json.dumps({
        "contract": "tdp-structural-clone-audit-v1",
        "min_lines": args.min_lines,
        "total_groups": len(groups),
        "cross_repo_groups": sum(row["cross_repo"] for row in groups),
        "largest_groups": groups[:args.limit],
        "note": "Exact body fingerprints are review candidates, not proof deletion is safe.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
