import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.research.build_b2b_review_queue import build

SNAPSHOT=json.loads((Path(__file__).resolve().parents[1]/"docs/roadmap/b2b_indexed_discovery_2026-11-15.json").read_text())
NOW=datetime.fromisoformat("2026-11-15T12:35:00+03:00")


def test_indexed_observations_cannot_promote():
    r=build(SNAPSHOT,checked_at=NOW)
    assert len(r["candidates"])==9
    assert r["qualified_current_opportunities"]==0 and not r["execution_allowed"]
    assert all(not x["bid_ready"] and not x["original_platform_verified"] and x["source_observed_at"] is None for x in r["candidates"])
    assert all(x["result_state"]!="PUBLIC_CANDIDATE_ONLY" for x in r["candidates"])


def test_fake_timestamp_discarded():
    row=SNAPSHOT["observations"][0]|{"source_observed_at":NOW.isoformat()}
    r=build(SNAPSHOT|{"observations":[row]},checked_at=NOW)["candidates"][0]
    assert r["result_reason"]=="source_status_timestamp_missing"


def test_provenance_and_unique_ids():
    row=SNAPSHOT["observations"][0]
    with pytest.raises(ValueError):
        build(SNAPSHOT|{"observations":[row,row]},checked_at=NOW)
    with pytest.raises(ValueError):
        build(SNAPSHOT|{"observations":[row|{"source_kind":"DIRECT_HTML"}]},checked_at=NOW)
