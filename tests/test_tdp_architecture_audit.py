"""Architectural anti-drift checks for staged Data Platform consolidation."""

from __future__ import annotations

from pathlib import Path

from scripts.ops.audit_tdp_boundaries import audit


def test_tender_agent_platform_client_is_only_cross_product_import():
    root = Path(__file__).resolve().parents[1]
    result = audit(root)
    assert result["contract"] == "tdp-architecture-audit-v1"
    assert result["tender_agent"]["python_files"] > 100
    assert result["tender_agent"]["direct_platform_imports_outside_client_facade"] == []
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
