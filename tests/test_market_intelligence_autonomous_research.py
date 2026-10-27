"""Regression tests for canonical MI-013 Power Quality research binding."""
import json
import os
from pathlib import Path

import pytest

from src.modules.market_intelligence.autonomous_research import run


def test_read_only_corpus_and_resume(tmp_path):
    corpus = Path(os.environ.get("MI013_PQ_CORPUS", "data/market_intelligence/power_quality"))
    if not (corpus / "verified_public_leads_20261027.v20.manifest.json").exists():
        pytest.skip("MI-013 v20 corpus not mounted in this checkout")
    out = tmp_path / "run"
    first = run(corpus=corpus, output=out)
    assert run(corpus=corpus, output=out) == first
    assert first["market_total_rub"] is None
    assert first["status"] == "completed_with_gaps"
    assert len((out / "research_events.jsonl").read_text().splitlines()) == 12
    assert json.loads((out / "manifest.json").read_text()) == first


def test_reject_writing_into_corpus(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    with pytest.raises(ValueError, match="outside"):
        run(corpus=corpus, output=corpus / "generated")
