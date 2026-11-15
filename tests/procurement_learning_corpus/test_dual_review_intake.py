"""Post-acceptance double-blind (independent reviewers) control without gold."""
from __future__ import annotations

import copy
import json
import stat
from datetime import UTC, datetime

import pytest

from scripts.procurement_llm.dual_review_intake import (
    DualReviewError,
    _read,
    compile_case,
    write_private_batch,
)
from scripts.procurement_llm.import_candidates import _manual_payload_items
from src.modules.procurement_learning_corpus.service import append_candidate


def manifest():
    shared = "a" * 64
    return {
        "schema": "procurement_dual_review_post_acceptance_v1",
        "procurement_ref": "eis:0163200000326005243",
        "source_manifest_sha256": shared,
        "source_document_sha256": ["b" * 64, "c" * 64],
        "technical_acceptance": {
            "status": "accepted",
            "record_ref": "TA-APR-PRODUCT-ACCEPTED-001",
            "evidence_sha256": "d" * 64,
            "accepted_at": "2026-10-19T09:00:00+03:00",
        },
        "reviews": [
            {
                "evaluator": "chatgpt",
                "run_ref": "chatgpt-review-0001",
                "model_label": "GPT-6/manual-independent",
                "source_manifest_sha256": shared,
                "prompt_sha256": "1" * 64,
                "output_artifact_sha256": "2" * 64,
                "completed_at": "2026-10-19T10:00:00+03:00",
                "claims": [
                    {
                        "field": "application_deadline",
                        "value_sha256": "3" * 64,
                        "source_document_sha256": ["b" * 64],
                    },
                    {
                        "field": "risks",
                        "value_sha256": "4" * 64,
                        "source_document_sha256": ["c" * 64],
                    },
                ],
            },
            {
                "evaluator": "tender_agent",
                "run_ref": "ta-run-0002",
                "model_label": "Gemma/Qwen locally",
                "source_manifest_sha256": shared,
                "prompt_sha256": "5" * 64,
                "output_artifact_sha256": "6" * 64,
                "completed_at": "2026-10-19T10:15:00+03:00",
                "claims": [
                    {
                        "field": "application_deadline",
                        "value_sha256": "3" * 64,
                        "source_document_sha256": ["b" * 64],
                    },
                    {
                        "field": "risks",
                        "value_sha256": "8" * 64,
                        "source_document_sha256": ["c" * 64],
                    },
                    {
                        "field": "technical_requirements",
                        "value_sha256": "9" * 64,
                        "source_document_sha256": ["b" * 64, "c" * 64],
                    },
                ],
            },
        ],
    }


def test_three_events_from_both_independent_reviews_and_comparison_not_gold(session):
    source = manifest()
    original = copy.deepcopy(source)
    result = compile_case(source)
    assert source == original
    assert result["disagreements_or_missing"] == 2
    assert result["field_comparison"] == {
        "application_deadline": "AGREE_NOT_GOLD",
        "risks": "DISAGREE_REQUIRES_HUMAN_REVIEW",
        "technical_requirements": "MISSING_IN_ONE_REVIEW",
    }
    assert result["human_adjudication_required"]
    assert result["training_promotion"] is False
    assert result["bid_authorized"] is False
    batch = result["candidate_batch"]
    assert batch["schema"] == "manual-candidate-import-v1"
    assert len(batch["items"]) == 3
    assert {v["event_type"] for v in batch["items"]} == {
        "post_acceptance_dual_chatgpt",
        "post_acceptance_dual_tender_agent",
        "post_acceptance_dual_comparison",
    }
    rows = _manual_payload_items(batch)
    assert all(row["training_status"] == "candidate_unreviewed" for row in rows)
    assert all(row["visibility_scope"] == "owner_internal" for row in rows)
    assert all(row["candidate_split"] == "manual_candidate_not_blind" for row in rows)
    assert all(append_candidate(session, row) for row in rows)
    assert not any(append_candidate(session, row) for row in rows)
    assert result == compile_case(source)


def test_agreement_without_disagreement_never_automatic_human_gold():
    src = manifest()
    src["reviews"][0]["claims"].append(copy.deepcopy(src["reviews"][1]["claims"][-1]))
    src["reviews"][1]["claims"][1]["value_sha256"] = "4" * 64
    result = compile_case(src)
    assert result["disagreements_or_missing"] == 0
    assert result["human_adjudication_required"] is True
    assert result["training_promotion"] is False
    assert set(result["field_comparison"].values()) == {"AGREE_NOT_GOLD"}
    for item in result["candidate_batch"]["items"]:
        assert item["human_adjudication_completed"] is False
        assert item["training_labels"] == "NOT_REVIEWED"


@pytest.mark.parametrize("patch", [
    lambda x: x["technical_acceptance"].update(status="pending"),
    lambda x: x["technical_acceptance"].update(status="rejected"),
    lambda x: x["technical_acceptance"].update(evidence_sha256="bad"),
    lambda x: x["technical_acceptance"].update(accepted_at="2026-10-19T09:00:00"),
    lambda x: x["reviews"][0].update(source_manifest_sha256="f" * 64),
    lambda x: x["reviews"][0].update(completed_at="2026-10-18T09:00:00+03:00"),
    lambda x: x["reviews"][1].update(evaluator="chatgpt"),
    lambda x: x["reviews"][1].update(run_ref="chatgpt-review-0001"),
    lambda x: x["reviews"][1].update(output_artifact_sha256="2" * 64),
    lambda x: x.update(source_document_sha256=["b" * 64, "b" * 64]),
    lambda x: x["reviews"][0]["claims"][0].update(source_document_sha256=["f" * 64]),
    lambda x: x["reviews"][0]["claims"][0].update(source_document_sha256=[]),
    lambda x: x["reviews"][0]["claims"][0].update(field="owner_legal_gold"),
    lambda x: x["reviews"][0]["claims"][0].update(value_sha256="not a digest"),
    lambda x: x["reviews"][0]["claims"][0].update(raw_text="SECRET"),
    lambda x: x["reviews"][0]["claims"].append(copy.deepcopy(x["reviews"][0]["claims"][0])),
    lambda x: x["reviews"][0].update(claims=[]),
    lambda x: x["reviews"][0].update(prompt_sha256="bad"),
    lambda x: x["reviews"][0].update(run_ref=""),
])
def test_fake_independence_incomplete_acceptance_or_out_of_source_citation_rejected(patch):
    src = manifest()
    patch(src)
    with pytest.raises((DualReviewError, ValueError, TypeError)):
        compile_case(src)


def test_comparison_fails_if_technical_acceptance_missing():
    src = manifest()
    src.pop("technical_acceptance")
    with pytest.raises(DualReviewError):
        compile_case(src)


def test_untrusted_raw_chat_not_entering_learning_payload():
    result = compile_case(manifest())
    text = json.dumps(result["candidate_batch"])
    assert "PRIVATE" not in text
    assert "raw_text" not in text
    assert "raw_chat" not in text
    assert '"model_gold": true' not in text
    assert "answer:" not in text


def test_private_materialization_replay_and_no_overwrite(tmp_path):
    data = compile_case(manifest())["candidate_batch"]
    file = tmp_path / "dual-reviews.json"
    write_private_batch(file, data, tmp_path)
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
    assert json.loads(file.read_text()) == data
    write_private_batch(file, data, tmp_path)
    with pytest.raises(DualReviewError):
        write_private_batch(file, {"different": "payload"}, tmp_path)
    with pytest.raises(DualReviewError):
        write_private_batch(tmp_path.parent / "outside.json", data, tmp_path)
    link = tmp_path / "indirect.json"
    link.symlink_to(file)
    with pytest.raises(DualReviewError):
        write_private_batch(link, data, tmp_path)


@pytest.mark.parametrize("raw", [
    '{"a":1,"a":2}',
    "not json",
])
def test_reject_duplicate_or_invalid_private_json(tmp_path, raw):
    item = tmp_path / "x.json"
    item.write_text(raw)
    with pytest.raises((DualReviewError, ValueError, json.JSONDecodeError)):
        _read(item)


def test_no_model_execution_or_live_db_requirements_for_dry_run():
    compiled = compile_case(manifest())
    assert compiled["candidate_batch"]["items"][0]["owner_bid_go"] is False
    assert datetime.fromisoformat(manifest()["technical_acceptance"]["accepted_at"]).tzinfo
    assert datetime.fromtimestamp(0, tz=UTC).tzinfo is not None
