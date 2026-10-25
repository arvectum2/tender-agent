"""SQL query behavior remains identical for all three legacy callers."""

from __future__ import annotations

from types import SimpleNamespace

from src.modules.execution_ledger.service import _latest_integration_task_set as ledger
from src.modules.external_execution.service import (
    _latest_integration_task_set as gateway,
)
from src.modules.operator_sessions.service import (
    _latest_integration_task_set as sessions,
)
from src.shared.control_package import latest_integration_task_set as canonical


class SessionFake:
    def __init__(self, task_set, records=()):
        self.task_set=task_set
        self.records=records
        self.calls=[]

    def scalar(self, statement):
        self.calls.append(("scalar", statement))
        return self.task_set

    def scalars(self, statement):
        self.calls.append(("scalars", statement))
        return iter(self.records)


def test_single_query_used_with_same_empty_and_populated_semantics():
    for call in [canonical, ledger, gateway, sessions]:
        empty=SessionFake(None)
        assert call(empty,"deal","DEAL-1") == (None, [])
        assert [what for what,_ in empty.calls] == ["scalar"]

        owned = SimpleNamespace(integration_task_set_id="ITS-01")
        row=SimpleNamespace(integration_task_id="IT-01")
        populated=SessionFake(owned, (row,))
        assert call(populated,"deal","DEAL-1") == (owned,[row])
        assert [what for what,_ in populated.calls] == ["scalar","scalars"]
