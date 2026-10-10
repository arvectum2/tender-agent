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

_TA_PLATFORM_IMPORT_PREFIXES = ("arvectum_data",)
_TA_SDK_IMPORT_PREFIXES = ("arvectum_data_client",)
_DP_FORBIDDEN_PREFIXES = (
    "src.",
    "tender_research.",
    "src.modules.tender_operator_agent_demo",
    "ai_corporation.",
)


def _matches_module(name: str, prefixes: tuple[str, ...]) -> bool:
    """Match a package *or* its descendants without matching unrelated names."""

    return any(name == prefix.rstrip(".") or name.startswith(prefix.rstrip(".") + ".")
               for prefix in prefixes)


def _imports(path: Path) -> list[str]:
    """Inspect static imports and literal dynamic imports, rejecting unreadable source."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        # An invalid Python file must not silently turn into a clean audit result.
        raise ValueError(f"Cannot audit imports in {path}") from exc
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
        elif isinstance(node, ast.Call) and node.args:
            literal = node.args[0]
            if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
                continue
            is_builtin = isinstance(node.func, ast.Name) and node.func.id == "__import__"
            is_importlib = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
            )
            if is_builtin or is_importlib:
                found.append(literal.value)
    return found


def _module_area_counts(paths: list[Path], src_root: Path, *, product: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        parts = path.relative_to(src_root).parts
        area = "/".join(parts[:2]) if product and parts[0] == "modules" and len(parts) > 1 else parts[0]
        counts[area] = counts.get(area, 0) + 1
    return dict(sorted(counts.items()))


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
    sdk_bypasses: list[str] = []
    allowed_facade = ta_root / "src/shared/data_platform.py"
    for path in ta_py:
        imported = _imports(path)
        if any(_matches_module(name, _TA_PLATFORM_IMPORT_PREFIXES) for name in imported):
            direct_imports.append(str(path.relative_to(ta_root)))
        if path != allowed_facade and any(
            _matches_module(name, _TA_SDK_IMPORT_PREFIXES) for name in imported
        ):
            sdk_bypasses.append(str(path.relative_to(ta_root)))
    result: dict[str, Any] = {
        "contract": "tdp-architecture-audit-v1",
        "tender_agent": {
            "python_files": len(ta_py),
            "module_area_counts": _module_area_counts(ta_py, ta_src, product=True),
            "operator_module_files": len(_python_files(operator_root)),
            "legacy_compatibility_files": [
                {"path": str(path.relative_to(ta_root)), "lines": len(path.read_text().splitlines())}
                for path in legacy
            ],
            "direct_platform_imports_outside_client_facade": direct_imports,
            "consumer_sdk_imports_outside_client_facade": sdk_bypasses,
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
            if any(_matches_module(name, _DP_FORBIDDEN_PREFIXES) for name in _imports(path))
        ]
        result["data_platform"] = {
            "python_files": len(dp_py),
            "module_area_counts": _module_area_counts(dp_py, dp_src, product=False),
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
        or result["tender_agent"]["consumer_sdk_imports_outside_client_facade"]
        or (result["data_platform"] or {}).get("forbidden_product_imports")
    ):
        raise SystemExit("Cross-product module ownership violation")


if __name__ == "__main__":
    main()
