"""Read-only evidence inventory must never promote unverified scoring to a GO/NO_GO."""
from __future__ import annotations

import json
from pathlib import Path

DATA = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/acceptance/qualification_scoring_corpus_inventory_2026-10-13.json"
).read_text(encoding="utf-8"))


def test_corpus_is_metadata_title_inventory_not_universal_scoring_evidence():
    cases = DATA["cases"]
    numbers = [x["procurement_number"] for x in cases]
    assert DATA["observed_metadata_records"] == 54
    assert DATA["unique_44fz_registry_numbers"] == 20
    assert len(cases) == 20 == len(set(numbers))
    assert all(len(n) == 19 and n.isdecimal() for n in numbers)
    assert DATA["source_boundary"].startswith("Docker volume ")
    assert DATA["scoring_document_title_candidate_count"] == 1
    assert DATA["independent_primary_scoring_evidence_count"] == 1
    assert DATA["other_19_explicit_no_scoring_rules_confirmed"] is False
    assert DATA["no_go_generalization_authorized"] is False
    assert DATA["recommended_new_parsers"] == "BLOCKED_PENDING_DISTINCT_PRIMARY_ORIGINAL_DOCUMENTS"
    assert all(x["download_time_sha256_receipt"] is False for x in cases)


def test_only_czn_source_is_independently_attested_and_no_other_auto_scores():
    cases = DATA["cases"]
    scored = [x for x in cases if x["auto_score_status"] != "NOT_ASSESSED"]
    assert len(scored) == 1
    assert scored[0]["procurement_number"] == "0348100024426000039"
    assert scored[0]["scoring_title_candidate"] is True
    assert scored[0]["auto_score_status"] == "SEPARATELY_ORIGINAL_VERIFIED_CZN_ONLY"
    assert DATA["historical_runs_with_new_download_time_archive_digest"] == 0
    assert DATA["ri223_scoring_evidence"] == "NOT_AUDITED_IN_THIS_VOLUME_SCAN"
    assert len(DATA["independent_scoring_document_sha256"]) == 64
    assert all(
        x["auto_score_status"] == "NOT_ASSESSED"
        for x in cases if x["procurement_number"] != "0348100024426000039"
    )
