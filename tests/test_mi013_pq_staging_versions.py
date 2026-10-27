"""The shared PQ exporter supports both legacy and lot-level count contracts."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "market_intelligence"
sys.path.insert(0, str(SCRIPTS))
try:
    from export_pq_data_platform import export_records
    from materialize_pq_research import materialize as v8
    from materialize_pq_research_v12 import materialize as v12
finally:
    sys.path.remove(str(SCRIPTS))


def test_v8_legacy_total_records_supported():
    assert len(export_records(v8())) == 60


def test_v12_lot_level_total_records_supported():
    result = export_records(v12())
    assert len(result) == 71
    assert len({r["external_id"] for r in result}) == 71


def test_exporter_refuses_conflicting_count_metadata():
    corpus = v12()
    corpus["verification_summary"]["total_records"] = 70
    with pytest.raises(ValueError, match="inconsistent"):
        export_records(corpus)


def test_exporter_refuses_missing_or_incorrect_count():
    corpus = v12()
    del corpus["verification_summary"]["total_lot_level_records"]
    with pytest.raises(ValueError, match="export count mismatch"):
        export_records(corpus)
    corpus["verification_summary"]["total_records"] = 70
    with pytest.raises(ValueError, match="export count mismatch"):
        export_records(corpus)
