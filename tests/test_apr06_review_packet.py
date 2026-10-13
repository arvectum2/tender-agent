"""APR-06 human review handoff must not fabricate legal or expert acceptance."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.acceptance.apr06_review_packet import build_queue, render_html

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/acceptance/apr06_candidate_pool_2026-10-09.json"
PREFILL = ROOT / "docs/acceptance/apr06_machine_prefill_2026-10-09.json"
BASE = "http://127.0.0.1:18083"


def payload():
    return json.loads(MANIFEST.read_text()), json.loads(PREFILL.read_text())


def test_real_fixtures_have_28_candidates_nine_machine_reports_and_zero_human_decisions():
    cases, reports = payload()
    queue, summary = build_queue(cases, reports, base_url=BASE)
    assert summary["candidate_total"] == 28
    assert summary["machine_reports"] == 9
    assert summary["human_reviewed"] == 0
    assert summary["commercial_acceptance"] == "BLOCKED_HUMAN_EVIDENCE_REQUIRED"
    assert len(queue) == 28
    assert all(case["human_decision"] is None for case in queue)
    assert all(case["official_document_sha256"] is None for case in queue)
    assert all(case["official_eis_revision"] is None for case in queue)
    assert sum(bool(x["private_report"]) for x in queue) == 9


def test_existing_saved_report_link_remains_private_auth_boundary():
    cases, reports = payload()
    queue, _ = build_queue(cases, reports, base_url=BASE)
    museum = next(x for x in queue if x["reg_number"] == "0372200172326000015")
    assert museum["private_report"].startswith(BASE + "/demo/tender-agent/runs/")
    assert museum["human_reviewed"] is False
    assert museum["machine_hint"] == "NEEDS_REVIEW"
    assert "report" in museum["private_report"]


def test_unavailable_documentation_stays_unverified_even_when_machine_has_data():
    cases, reports = payload()
    queue, summary = build_queue(cases, reports, base_url=BASE)
    partial = next(x for x in queue if x["reg_number"] == "0348100024426000039")
    assert partial["machine_status"] == "PARTIAL_SOURCE_TEXT"
    assert summary["source_incomplete"] >= 19
    assert partial["human_decision"] is None


@pytest.mark.parametrize("target", [
    "https://arvectum.com", "http://evil.example:18083",
    "http://127.0.0.2:18083", "http://127.0.0.1:18083/path",
    "http://admin:password@127.0.0.1:18083",
    "http://127.0.0.1:80", "http://127.0.0.1:18083?token=abc",
])
def test_no_non_loopback_or_insecure_base_urls(target):
    manifest, prefill = payload()
    with pytest.raises(ValueError, match="localhost HTTP port"):
        build_queue(manifest, prefill, base_url=target)


def test_untrusted_subject_and_machine_fields_are_escaped():
    cases, reports = payload()
    cases["cases"][0]["subject"] = "<img src=x onerror=alert(1)>"
    reports["cases"][0]["machine_decision"] = "<script>alert(1)</script>"
    queue, summary = build_queue(cases, reports, base_url=BASE)
    rendered = render_html(queue, summary)
    assert "<script>alert(1)</script>" not in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert "&lt;img" in rendered
    assert "&lt;script" in rendered
    assert "human_decision" not in rendered
    assert "НЕ ПРИНЯТО" in rendered


def test_manifest_duplicates_and_unknown_machine_report_fail_closed():
    cases, reports = payload()
    cases["cases"].append(dict(cases["cases"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        build_queue(cases, reports, base_url=BASE)
    cases, reports = payload()
    reports["cases"][0]["notice"] = "9999999999999999999"
    with pytest.raises(ValueError, match="absent"):
        build_queue(cases, reports, base_url=BASE)


def test_machine_run_id_is_not_used_as_untrusted_html_url():
    cases, reports = payload()
    reports["cases"][0]["run_id"] = "https://evil.invalid/"
    with pytest.raises(ValueError, match="saved run"):
        build_queue(cases, reports, base_url=BASE)


def test_cli_writes_private_html_without_overwriting_or_fake_human_data(tmp_path):
    path = tmp_path / "review-queue.html"
    cmd = [
        sys.executable, "-m", "scripts.acceptance.apr06_review_packet",
        "--manifest", str(MANIFEST), "--prefill", str(PREFILL),
        "--output", str(path),
    ]
    result = subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
    summary = json.loads(result.stdout)
    assert summary["human_reviewed"] == 0
    assert summary["machine_reports"] == 9
    assert summary["candidate_total"] == 28
    assert path.exists()
    assert os.stat(path).st_mode & 0o777 == 0o600
    markup = path.read_text()
    assert markup.count("<tr>") == 29
    assert "127.0.0.1:18083" in markup
    before = path.read_bytes()
    second = subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True, text=True)
    assert second.returncode != 0
    assert path.read_bytes() == before
