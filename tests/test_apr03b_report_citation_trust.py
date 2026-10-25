"""Report-only references are unverified, even with plausible locator fields."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src/modules/tender_operator_agent_demo/assets/operator_workspace.js"
)


def test_risk_and_readiness_report_claims_are_not_treated_as_verified():
    source = SOURCE.read_text(encoding="utf-8")
    section = source.split("  function renderEvidence(", 1)[1].split(
        "  function renderSections(", 1
    )[0]
    assert "const grounded = validCitations(item.evidence).length > 0;" not in section
    assert "Статус отчёта: " in section
    assert "НЕ подтверждено оригиналом" in section
    assert "UNKNOWN · нет подтверждения по оригиналу" in section
    assert "renderCitations(block, item.evidence)" in section
    assert "originalVerified: true" not in section


def test_only_notice_verified_facts_enable_source_verified_rendering():
    source = SOURCE.read_text(encoding="utf-8")
    assert "renderCitations(block, verified ? f.evidence : [], {originalVerified: verified})" in source
    assert "f.status === 'KNOWN' && validCitations(f.evidence).length > 0" in source
    assert "Указанный в отчёте источник (НЕ сверено с оригиналом): " in source
    assert "Проверенный оригинал XML ЕИС: " in source


def test_changed_browser_javascript_syntax_is_valid():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed on this runner")
    result = subprocess.run(
        [node, "--check", str(SOURCE)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
