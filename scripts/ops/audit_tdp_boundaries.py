"""Read-only Tender Agent / Data Platform architecture and ownership inventory.

Runnable in CI without the other repository: --data-platform-root is optional.
No imports are executed; AST is used to avoid touching live services/credentials.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

TA_ROOT = Path(__file__).resolve().parents[2]

_TA_PLATFORM_IMPORT_PREFIXES = ("arvectum_data.",)
_DP_FORBIDDEN_PREFIXES = (
    "src.",
    "tender_research.",
    "src.modules.tender_operator_agent_demo",
    "ai_corporation.",
)


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
    return found


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if not any(
        segment in {"__pycache__", ".venv", ".git"} for segment in path.parts
    ))


def audit(ta_root: Path, dp_root: Path | None = None) -> dict[str, Any]:
    ta_src = ta_root / "src"
    ta_py = _python_files(ta_src)
    operator_root = ta_src / "modules/tender_operator_agent_demo"
    legacy = [
        path for path in _python_files(operator_root)
        if path.name.endswith("_legacy.py")
    ]
    platform_owned = [
        "generic document extraction + chunking",
        "resource/document/chunk identity and source provenance",
        "OCR/VLM, embedding, vector/lexical/hybrid indexing/search",
        "generic consumer SDK, API and scope isolation",
    ]
    ta_owned = [
        "44-FZ/223-FZ notice revision selection, EIS SOAP and procurement rules",
        "supplier/commercial eligibility, GO/NO-GO and human approval",
        "procurement-specific evidence/decision-core/report presentation",
        "browser operator workflow, PDF/DOCX tender deliverables",
    ]
    direct_imports: list[str] = []
    for path in ta_py:
        if any(name.startswith(_TA_PLATFORM_IMPORT_PREFIXES) for name in _imports(path)):
            direct_imports.append(str(path.relative_to(ta_root)))
    result: dict[str, Any] = {
        "contract": "tdp-architecture-audit-v1",
        "tender_agent": {
            "python_files": len(ta_py),
            "operator_module_files": len(_python_files(operator_root)),
            "legacy_compatibility_files": [
                {"path": str(path.relative_to(ta_root)), "lines": len(path.read_text().splitlines())}
                for path in legacy
            ],
            "direct_platform_imports_outside_client_facade": direct_imports,
        },
        "ownership": {
            "data_platform": platform_owned,
            "tender_agent": ta_owned,
        },
        "data_platform": None,
    }
    if dp_root is not None:
        dp_src = dp_root / "src/arvectum_data"
        dp_py = _python_files(dp_src)
        product_imports = [
            str(path.relative_to(dp_root))
            for path in dp_py
            if any(name.startswith(_DP_FORBIDDEN_PREFIXES) for name in _imports(path))
        ]
        result["data_platform"] = {
            "python_files": len(dp_py),
            "forbidden_product_imports": product_imports,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tender-agent-root", type=Path, default=TA_ROOT)
    parser.add_argument("--data-platform-root", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = audit(args.tender_agent_root.resolve(), (
        args.data_platform_root.resolve() if args.data_platform_root else None
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.strict and (
        result["tender_agent"]["direct_platform_imports_outside_client_facade"]
        or (result["data_platform"] or {}).get("forbidden_product_imports")
    ):
        raise SystemExit("Cross-product module ownership violation")


if __name__ == "__main__":
    main()
