"""APR-07 acceptance of honest denominators and no inferred production quality."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.quality.apr07_snapshot import main
from src.modules.quality_slo.snapshot import (
    QualityEvidenceError,
    build_snapshot,
    data_platform_evidence,
    load,
    product_metrics,
)
from src.modules.quality_slo.snapshot import (
    ratio as rate,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPT = ROOT / "docs" / "acceptance"


def inputs():
    names = (
        "apr06_real_probe_receipts_2026-10-09.json",
        "apr06_machine_prefill_2026-10-09.json",
        "apr06_independent_gpt6_audit_2026-10-09.json",
    )
    return [load(ACCEPT / name)[0] for name in names]


def test_real_receipt_denominators_and_human_unknowns():
    p = product_metrics(*inputs())
    m = p["metrics"]
    assert p["cases"] == 20
    assert p["source_files"] == 168
    assert m["document_acquisition_any_file"]["numerator"] == 17
    assert m["analyzable_intakes"]["numerator"] == 9
    assert m["file_text_available_flag"]["numerator"] == 109
    assert m["file_text_available_flag"]["denominator"] == 118
    assert m["machine_decision_citation_presence"]["value"] == 1.0
    assert m["human_verified_citation_accuracy"]["value"] is None
    assert m["human_override_rate"]["state"] == "NOT_MEASURED"
    assert m["ocr_fallback_rate"]["value"] is None
    assert p["attributed_human_reviews"] == 0


@pytest.mark.parametrize("kind", [
    "duplicate_case", "file_hash", "wrong_run", "pretend_human", "text_denominator",
    "missing_source", "false_report",
])
def test_corruption_and_fabricated_labels_fail_closed(kind):
    receipt, report, audit = copy.deepcopy(inputs())
    if kind == "duplicate_case":
        receipt["cases"].append(copy.deepcopy(receipt["cases"][0]))
    elif kind == "file_hash":
        receipt["cases"][0]["document_files"][0]["sha256"] = "notsha"
    elif kind == "wrong_run":
        report["cases"][0]["run_id"] = "different-run"
    elif kind == "pretend_human":
        audit["human_operator_review"] = True
    elif kind == "text_denominator":
        report["cases"][0]["source_text_available"] = 9999
    elif kind == "missing_source":
        report["cases"][0]["notice"] = "0000000000000000000"
    elif kind == "false_report":
        receipt["cases"][0]["status"] = "docs_required"
    with pytest.raises(QualityEvidenceError):
        product_metrics(receipt, report, audit)


def test_rates_do_not_divide_by_zero():
    assert rate(None, None, "no_true_labels")["value"] is None
    assert rate(0, 0, "none")["state"] == "NOT_MEASURED"
    with pytest.raises(QualityEvidenceError):
        rate(1, 0, "unsafe")


def test_snapshot_deterministic_and_absent_dp_truth():
    left = build_snapshot(ROOT)
    assert left == build_snapshot(ROOT)
    assert left["data_platform"]["status"] == "NOT_MEASURED_NO_DP_REPORT"
    assert left["models_downloaded"] is False
    assert left["models_promoted"] is False
    assert left["human_quality_approved"] is False
    assert len(left["snapshot_sha256"]) == 64


def test_cli_refuses_overwrite(tmp_path):
    out = tmp_path / "snapshot.json"
    assert main(["--output", str(out)]) == 0
    first = out.read_bytes()
    assert main(["--output", str(out)]) == 2
    assert first == out.read_bytes()


def _dp_fixture(root):
    suite = "a" * 64
    for suffix in ("0.6b", "4b", "8b"):
        (root / f"embedding-{suffix}.json").write_text(json.dumps({
            "suite_sha256": suite, "site_corpus_hash": "c" * 64,
            "docs": 45, "queries": 12, "top1": 0.5, "mrr": 0.6,
            "ndcg_at5": 0.8, "recall_at5": 0.9, "model": f"Qwen {suffix}",
        }))
    (root / "reranker-qwen3-0.6b-vs-bge.json").write_text("{}")
    (root / "ocr-qwen3vl4b-vs-tesseract.json").write_text(json.dumps({
        "summary": {"tesseract": {"cases": 2, "mean_cer": 0.2, "mean_wer": 0.3},
                    "qwen3vl": {"cases": 2, "mean_cer": 0.1, "mean_wer": 0.2}}}))
    for suffix in ("4b", "9b"):
        (root / f"reasoning-qwen35-{suffix}.json").write_text(json.dumps({
            "model": suffix, "suite_sha256": "d" * 64,
            "summary": {"cases": 5, "combined_pass_rate": 1.0}}))


def test_dp_bridge_is_offline_and_only_exploratory(tmp_path):
    _dp_fixture(tmp_path)
    result = data_platform_evidence(tmp_path)
    assert len(result["source_result_sha256"]) == 7
    assert result["embeddings"]["embedding-4b.json"]["queries"] == 12
    assert result["downloads_performed_by_tender_agent"] is False
    assert result["model_promotion"].startswith("BLOCKED")


def test_dp_mixed_corpus_rejected(tmp_path):
    _dp_fixture(tmp_path)
    p = tmp_path / "embedding-8b.json"
    d = json.loads(p.read_text())
    d["site_corpus_hash"] = "f" * 64
    p.write_text(json.dumps(d))
    with pytest.raises(QualityEvidenceError, match="incomparable"):
        data_platform_evidence(tmp_path)


def test_dp_symlink_rejected(tmp_path):
    target = tmp_path / "doc.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(QualityEvidenceError):
        load(link)


def test_timed_analysis_has_source_binding_and_never_says_human(tmp_path):
    from src.modules.quality_slo.snapshot import include_bounded_analysis_latency

    data = build_snapshot(ROOT)
    ids = data["procurement"]["machine_run_ids"]
    p = tmp_path / "timings.jsonl"
    p.write_text("".join(
        json.dumps({
            "run_id": rid, "elapsed_seconds": index + 1.0,
            "external_actions": False, "human_review_completed": False,
        }) + "\n" for index, rid in enumerate(ids)
    ))
    result = include_bounded_analysis_latency(data, p)
    assert result["latency_observation"]["p95_seconds_nearest_rank"] == len(ids)
    assert result["latency_observation"]["run_count"] == len(ids)
    assert result["snapshot_sha256"] != data["snapshot_sha256"]
    p.write_text(p.read_text().replace(ids[0], "bogus-id"))
    with pytest.raises(QualityEvidenceError, match="source run IDs mismatch"):
        include_bounded_analysis_latency(data, p)


def test_source_roster_has_real_hashes_but_no_model_decision_truth():
    from src.modules.quality_slo.corpus import build_candidate_roster

    roster = build_candidate_roster(ROOT)
    assert roster["number_of_candidates"] == 9
    assert roster["all_cases_are_human_gold"] is False
    assert len(roster["roster_sha256"]) == 64
    for case in roster["cases"]:
        assert case["label_state"] == "AI_CURATED_SILVER_NOT_HUMAN_GOLD"
        assert case["verified_answer_labels"] is None
        assert case["human_review_completed"] is False
        assert case["attachment_revision_binding_verified"] is False
        assert len(case["notice_sha256"]) == 64


def test_source_roster_rejects_unbound_notice(tmp_path):
    from src.modules.quality_slo.corpus import build_candidate_roster

    base = tmp_path / "docs" / "acceptance"
    base.mkdir(parents=True)
    originals, _, audit = inputs()
    audit["cases"][0]["latest_archived_notice"]["source_sha256"] = "1" * 64
    (base / "apr06_real_probe_receipts_2026-10-09.json").write_text(json.dumps(originals))
    (base / "apr06_independent_gpt6_audit_2026-10-09.json").write_text(json.dumps(audit))
    with pytest.raises(QualityEvidenceError, match="notice hash"):
        build_candidate_roster(tmp_path)
