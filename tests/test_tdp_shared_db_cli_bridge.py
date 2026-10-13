"""Both database diagnostic CLIs use exactly one shared source of truth."""

from __future__ import annotations

import argparse

from src.shared.db import cli as shared_db_cli
from src.tender_research import cli as tender_cli


def test_tender_check_db_uses_shared_implementation(monkeypatch):
    invoked = []
    monkeypatch.setattr(shared_db_cli, "cmd_check_db", lambda: invoked.append("shared"))
    tender_cli.cmd_check_db(argparse.Namespace(command="check-db"))
    assert invoked == ["shared"]
