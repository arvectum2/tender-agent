"""Already committed receipts are linked even if the batch later aborts."""
from __future__ import annotations

import hashlib
import json
from unittest.mock import Mock

import pytest

from scripts.research.autonomous_runner import Blocked, Runner


@pytest.mark.parametrize('fail', [True, False])
def test_member_batch_registers_committed_partial_results(tmp_path, fail):
    runner = Runner.__new__(Runner)
    runner.root = runner.sibur = tmp_path
    runner.member_plan = tmp_path / 'plan.json'
    runner.member_plan.write_text('{}')
    runner.member_plan_sha = hashlib.sha256(runner.member_plan.read_bytes()).hexdigest()
    runner.member_batch_limit = 3
    lane = {'archive_synced_count': 7}
    runner.state = {'lanes': {'sibur': lane}}
    before = {str(i): {} for i in range(7)}
    after = {**before, 'new': {}}
    runner.local_index = Mock(side_effect=[before, before, after])
    runner.reconcile_index = Mock()
    runner.stop_requested = Mock(return_value=False)
    runner.gate = Mock(return_value=tmp_path / 'gate.json')
    runner.backup_ta = Mock()
    runner.update = lambda _lane, **values: lane.update(values)

    linked = {'updated': 1, 'members': 1, 'procedure_member_pairs': 1,
              'source_links': 1, 'registry_sha256': 'a' * 64}
    calls = []

    def command(_lane, step, args, cwd, timeout):
        calls.append(step)
        if step.endswith('_extract'):
            return b'planned 2'
        if step.endswith('_index'):
            if fail:
                raise Blocked('partial index batch')
            return b'planned 1'
        if step == 'member registry':
            return json.dumps(linked).encode()
        if step == 'member registry replay':
            return json.dumps({**linked, 'updated': 0}).encode()
        raise AssertionError(step)

    def sync(index):
        assert index == after
        lane['archive_synced_count'] = len(index)

    runner.cmd = command
    if fail:
        with pytest.raises(Blocked, match='partial index batch'):
            runner.member_index_pilot(sync)
        assert lane['member_pilot_status'] == 'partial_reconciled_blocked'
        assert lane['member_partial_registry'] == linked
        assert lane['index_inflight'] is True
        assert 'member_pilot_completed_sha256' not in lane
    else:
        assert runner.member_index_pilot(sync)
        assert lane['member_pilot_status'] == 'completed'
        assert lane['index_inflight'] is False
        assert lane['member_pilot_completed_sha256'] == runner.member_plan_sha
    assert calls[-2:] == ['member registry', 'member registry replay']
    assert lane['archive_synced_count'] == len(after)
    runner.backup_ta.assert_called_once_with('sibur')
