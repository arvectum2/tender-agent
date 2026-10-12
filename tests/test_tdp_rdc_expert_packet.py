"""Contract tests for offline Gemma -> ChatGPT via RDC evidence packets."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.acceptance.build_rdc_expert_packet import build_review_packet

NUMBER = "0376300000126000193"
RUN = "toa-run-20261009052414-56bbe6"
FILE = "file-06-contract_draft.txt"
QUOTE = "Обеспечение исполнения обязательств"
TEXT = (
    "Раздел 1. Обеспечение исполнения обязательств осуществляется в размере "
    "5 (пяти) % начальной цены контракта. В случае снижения на 25% "
    "предусмотрена альтернатива при подтверждении добросовестности."
)


def _inputs(tmp_path: Path, text: str = TEXT):
    runs = tmp_path / "runs"
    original = runs / RUN / "normalized" / FILE
    original.parent.mkdir(parents=True)
    original.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode()).hexdigest()
    manifest = [{
        "reg_number": NUMBER, "run_id": RUN,
        "source_evidence": [{"source": FILE, "sha256_normalized_text": digest}],
    }]
    claim = {
        "source": FILE, "quote": QUOTE,
        "interpretation": "Security automatically doubles at a lower bid.",
    }
    transcript = {"cases": [{"reg_number": NUMBER, "claims": [claim]}]}
    return runs, original, transcript, manifest


def test_exact_source_quote_has_context_but_never_claims_semantics(tmp_path: Path):
    runs, _original, transcript, manifest = _inputs(tmp_path)
    packet = build_review_packet(transcript, manifest, runs)
    evidence = packet["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "LITERAL_MATCH"
    assert evidence["normalized_char_offset"] == TEXT.index(QUOTE)
    assert evidence["source_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert QUOTE in evidence["bounded_source_context"]
    assert "добросовестности" in evidence["bounded_source_context"]
    assert evidence["semantic_review"] == "REQUIRES_CHATGPT_IN_CHAT"
    assert evidence["legal_review"] == "UNKNOWN"
    assert evidence["go_eligible"] is False
    assert packet["semantic_review"] == "NOT_PERFORMED_BY_THIS_TOOL"
    assert packet["go_eligible"] is False


def test_false_paraphrase_cannot_pass_literal_check(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path)
    transcript["cases"][0]["claims"][0]["quote"] = "Неопровержимый запрет на участие"
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "QUOTE_MISSING"
    assert "bounded_source_context" not in evidence


def test_repeated_quote_ambiguous_not_verified(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path, TEXT + "\n" + QUOTE)
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "QUOTE_AMBIGUOUS"
    assert evidence["occurrences"] == 2


def test_whitespace_variant_needs_expert_and_cannot_count_as_literal(tmp_path: Path):
    variant = TEXT.replace("Обеспечение исполнения обязательств", "Обеспечение\nисполнения\u00a0обязательств")
    runs, _, transcript, manifest = _inputs(tmp_path, variant)
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "QUOTE_FORMAT_VARIANT"
    assert evidence["semantic_review"] == "REQUIRES_CHATGPT_IN_CHAT"
    assert evidence["go_eligible"] is False
    assert "normalized_char_offset" not in evidence


def test_modified_original_is_rejected_before_reading_source_context(tmp_path: Path):
    runs, original, transcript, manifest = _inputs(tmp_path)
    original.write_text("ПОДМЕНЕНО " + TEXT)
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "SOURCE_SHA256_MISMATCH"
    assert "bounded_source_context" not in evidence


def test_unknown_original_is_not_invented(tmp_path: Path):
    runs, original, transcript, manifest = _inputs(tmp_path)
    original.unlink()
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "ORIGINAL_UNAVAILABLE"


def test_filename_traversal_cannot_escape_cached_source_tree(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path)
    transcript["cases"][0]["claims"][0]["source"] = "../../secret.txt"
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "SOURCE_NAME_REJECTED"


def test_manifest_does_not_attest_missing_source(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path)
    manifest[0]["source_evidence"] = []
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "SOURCE_NOT_IN_MANIFEST"


def test_invalid_run_identity_does_not_escape_runs_root(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path)
    manifest[0]["run_id"] = "../../outside"
    case = build_review_packet(transcript, manifest, runs)["cases"][0]
    assert case["source_status"] == "SOURCE_IDENTITY_UNAVAILABLE"
    assert case["claims"][0]["evidence"]["status"] == "SOURCE_IDENTITY_UNAVAILABLE"


def test_symlinks_refused_even_with_matching_hash(tmp_path: Path):
    runs, original, transcript, manifest = _inputs(tmp_path)
    linked = tmp_path / "original-doc.txt"
    original.rename(linked)
    original.symlink_to(linked)
    evidence = build_review_packet(transcript, manifest, runs)["cases"][0]["claims"][0]["evidence"]
    assert evidence["status"] == "ORIGINAL_UNAVAILABLE"


@pytest.mark.parametrize("length", [41, 41_000])
def test_unbounded_case_list_rejected(tmp_path: Path, length: int):
    runs, _, transcript, manifest = _inputs(tmp_path)
    with pytest.raises(ValueError):
        build_review_packet({"cases": [transcript["cases"][0]] * length}, manifest, runs)


def test_unbounded_claims_and_invalid_procurement_rejected(tmp_path: Path):
    runs, _, transcript, manifest = _inputs(tmp_path)
    transcript["cases"][0]["claims"] *= 65
    with pytest.raises(ValueError):
        build_review_packet(transcript, manifest, runs)
    transcript["cases"][0]["claims"] = []
    transcript["cases"][0]["reg_number"] = "../37"
    with pytest.raises(ValueError):
        build_review_packet(transcript, manifest, runs)
