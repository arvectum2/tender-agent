"""Architectural anti-drift checks for staged Data Platform consolidation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ops.audit_tdp_boundaries import audit


def test_tender_agent_platform_client_is_only_cross_product_import():
    root = Path(__file__).resolve().parents[1]
    result = audit(root)
    assert result["contract"] == "tdp-architecture-audit-v1"
    assert result["tender_agent"]["python_files"] > 100
    assert result["tender_agent"]["direct_platform_imports_outside_client_facade"] == []
    assert result["tender_agent"]["consumer_sdk_imports_outside_client_facade"] == []
    assert sum(result["tender_agent"]["module_area_counts"].values()) == (
        result["tender_agent"]["python_files"]
    )
    assert any(
        name["path"].endswith("upload_service_legacy.py")
        for name in result["tender_agent"]["legacy_compatibility_files"]
    )


def test_data_platform_never_imports_product_logic_when_available(tmp_path):
    ta = tmp_path / "ta"
    dp = tmp_path / "dp"
    (ta / "src").mkdir(parents=True)
    pkg = dp / "src/arvectum_data"
    pkg.mkdir(parents=True)
    (pkg / "good.py").write_text("from datetime import datetime\n", encoding="utf-8")
    clean = audit(ta, dp)
    assert clean["data_platform"]["forbidden_product_imports"] == []
    (pkg / "bad.py").write_text(
        "from tender_research.some_module import thing\n", encoding="utf-8"
    )
    dirty = audit(ta, dp)
    assert dirty["data_platform"]["forbidden_product_imports"] == [
        "src/arvectum_data/bad.py"
    ]


def test_product_imports_cannot_bypass_sdk_facade(tmp_path):
    root = tmp_path / "ta"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "root.py").write_text("from arvectum_data import processing\n", encoding="utf-8")
    (src / "literal.py").write_text(
        'import importlib\nx = importlib.import_module("arvectum_data.search")\n',
        encoding="utf-8",
    )
    (src / "sdk.py").write_text("import arvectum_data_client\n", encoding="utf-8")
    (src / "builtin.py").write_text(
        'x = __import__("arvectum_data.processing")\n', encoding="utf-8"
    )
    result = audit(root)
    assert result["tender_agent"]["direct_platform_imports_outside_client_facade"] == [
        "src/builtin.py", "src/literal.py", "src/root.py"
    ]
    assert result["tender_agent"]["consumer_sdk_imports_outside_client_facade"] == [
        "src/sdk.py"
    ]


def test_unparseable_sources_fail_closed(tmp_path):
    root = tmp_path / "ta"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "broken.py").write_text("def missing(:\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot audit imports"):
        audit(root)
