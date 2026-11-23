"""Protect bounded live DP SDK evidence from being misread as release approval."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml(relative):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf8"))


def test_bounded_dp_probe_completed_after_protected_ci_merge():
    root = _yaml(".agent/current-task.yaml")
    index = root["dp_live_sdk_readonly_2026_11_22"]
    child = _yaml(index["checkpoint"])
    assert index["status"] == child["status"] == "completed"
    assert index["production_writes"] is False
    assert child["production_writes"] is False
    assert child["external_http_requests"] is False
    assert child["deployment_authorized"] is False
    assert child["remaining"] == []
    assert child["protected_exact_ci"] == "10_of_10_success"
    assert child["protected_merge_commit"] == "d1de9c398d30fff738e89be1513c7caa4db319f6"
    assert child["production_deployed"] is False
    assert any(
        "55b7f94f50391eff7d4f920accbf07620a29ece913254826eff2cdf40ca9ac80" in item
        for item in child["completed"]
    )


def test_owner_runtime_release_and_sustained_dp_slo_stay_blocked():
    root = _yaml(".agent/current-task.yaml")
    parent = root["core_runtime_release_2026_11_22"]
    release = _yaml(parent["checkpoint"])
    assert parent["status"] == release["status"] == "blocked"
    assert parent["production_deployed"] is release["production_deployed"] is False
    assert "sustained_DP_HTTP_SDK_reliability" in release["remaining"]
    assert "DP_ingest_p95_at_most_10000ms_representative_samples" in release["remaining"]
    assert release["upstream_dp_ingest_slo_issue"] == "arvectum2/data-platform#133"
    assert release["dp_readiness_private_sha256"] == "1b3fedc89a25e348e6bdfb0c7f47567e447f20687ec0336c746728911284310d"
    assert "independent_real_Gemma_acceptance" in release["remaining"]
    assert "owner_exact_release_approval" in release["remaining"]
    assert "authorized_runtime_deploy" in release["remaining"]
    assert root["status"] == "in_progress"


def test_unchanged_other_source_and_pitr_gates():
    root = _yaml(".agent/current-task.yaml")
    for key in (
        "pitr_seven_day_2026_11_22",
        "dtr679_current_originals_2026_11_22",
        "sibur_ppt_current_source_2026_11_22",
        "apr06_qualification_release_2026_11_22",
    ):
        index = root[key]
        assert index["status"] == _yaml(index["checkpoint"])["status"] == "blocked"
