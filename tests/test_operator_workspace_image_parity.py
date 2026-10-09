"""Regression: PR #259 tests passed but two stale image files broke real Safari analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ops.verify_operator_workspace_preview import (
    manifest_differences,
    source_manifest,
    tree_manifest,
)


def test_private_dockerfile_overlays_complete_operator_module():
    root = Path(__file__).resolve().parents[1]
    dockerfile = root / "deploy/pilot/Dockerfile.operator-workspace-preview"
    text = dockerfile.read_text()
    assert "RUN rm -rf /app/src /app/scripts" in text
    assert "COPY --chown=app:app src/ /app/src/" in text
    assert "COPY --chown=app:app scripts/ /app/scripts/" in text
    assert 'org.opencontainers.image.revision' in text
    assert "COPY src/modules/tender_operator_agent_demo/" not in text
    assert text.strip().endswith("USER app")


def test_operator_runtime_manifest_detects_exactly_stale_backend_files(tmp_path: Path):
    src = tmp_path / "src/modules/tender_operator_agent_demo"
    src.mkdir(parents=True)
    (src / "upload_service_legacy.py").write_text("version_is_optional = True")
    (src / "procurement_intake_service.py").write_text("source = 'checked-out-main'")
    (src / "assets").mkdir()
    (src / "assets/operator_workspace.js").write_text("const run = 'verified';")
    expected = source_manifest(tmp_path)
    assert set(expected) == {
        "upload_service_legacy.py",
        "procurement_intake_service.py",
        "assets/operator_workspace.js",
    }
    runtime = dict(expected)
    runtime["upload_service_legacy.py"] = "stale-server-bytecode"
    runtime["procurement_intake_service.py"] = "stale-eis-adapter"
    assert manifest_differences(expected, runtime) == [
        "procurement_intake_service.py", "upload_service_legacy.py"
    ]
    assert manifest_differences(expected, expected) == []


def test_operator_runtime_manifest_includes_private_html_css_and_js(tmp_path: Path):
    src = tmp_path / "src/modules/tender_operator_agent_demo/assets"
    src.mkdir(parents=True)
    for name in ["operator_workspace.html", "operator_workspace.css", "operator_workspace.js"]:
        (src / name).write_text("original")
    expected = source_manifest(tmp_path)
    assert sorted(expected) == [
        "assets/operator_workspace.css",
        "assets/operator_workspace.html",
        "assets/operator_workspace.js",
    ]


def test_operator_runtime_manifest_missing_source_fails_closed(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Missing operator source"):
        source_manifest(tmp_path)


def test_full_source_manifest_includes_generic_platform_wrapper_and_scripts(tmp_path: Path):
    operator = tmp_path / "src/modules/tender_operator_agent_demo"
    operator.mkdir(parents=True)
    (operator / "upload_service.py").write_text("operator")
    shared = tmp_path / "src/shared"
    shared.mkdir()
    (shared / "document_processing.py").write_text("platform-sdk-consumer")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_tender_operator_pilot.py").write_text("current-script")
    expected = {
        **tree_manifest(tmp_path, Path("src")),
        **tree_manifest(tmp_path, Path("scripts")),
    }
    assert set(expected) == {
        "src/modules/tender_operator_agent_demo/upload_service.py",
        "src/shared/document_processing.py",
        "scripts/run_tender_operator_pilot.py",
    }
    actual = dict(expected)
    actual["src/shared/document_processing.py"] = "stale-platform-consumer"
    assert manifest_differences(expected, actual) == ["src/shared/document_processing.py"]


def test_full_source_manifest_fails_if_scripts_missing(tmp_path: Path):
    (tmp_path / "src").mkdir()
    with pytest.raises(RuntimeError, match="Missing operator source"):
        tree_manifest(tmp_path, Path("scripts"))
