"""Fail-closed daily Gazprom EnergoHolding source snapshot regression."""
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.research import run_geh_fresh_cycle as cycle
from scripts.research.ingest_verified_geh_snapshot import process


def test_snapshot_name_stable_date():
    assert cycle.snapshot_name(datetime(2026, 11, 22, 10, 30, tzinfo=UTC)) == 'geh-active-refresh-20261122T103000Z'


def test_plan_preserves_rejected_and_duplicate_observations(tmp_path: Path):
    sample = [
        {'observation': {'external_id': 'etp:1'}},
        {'observation': {'external_id': 'etp:1'}},
        {'observation': {'external_id': 'etp:2'}},
    ]
    def normalize(row):
        if row['observation']['external_id'] == 'etp:2':
            raise ValueError('source stage/date mismatch')
        return row['observation']
    with patch.object(cycle, 'replay', return_value=sample), patch.object(cycle, 'normalize', side_effect=normalize):
        approved, review = cycle.plan_for(tmp_path)
    assert len(approved) == 1
    assert [r['reason'] for r in review] == ['duplicate procurement identity across pages', 'source stage/date mismatch']


def test_ingest_refuses_other_directories(tmp_path: Path):
    with pytest.raises(ValueError, match='outside verified GEH capture root'):
        process(tmp_path / 'geh-active-refresh-20261122T103000Z')
