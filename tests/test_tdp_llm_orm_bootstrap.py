"""Controlled LLM adapter must register all ORM tables in a pristine process.

Without the full model registry import, Base.metadata.create_all dies on
NoReferencedTableError before the first model invocation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_isolated_controlled_workflow_bootstraps_its_own_orm(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "isolated-run.db"
    script = """
from pathlib import Path
from types import SimpleNamespace
from src.modules.controlled_llm_prebid import service as controlled
from src.modules.tender_operator_agent_demo.operator_llm_workflow import run_controlled_operator_llm
from src.shared.config.settings import Settings
import sys
controlled.run_controlled_tender_operator_workflow=lambda *args, **kwargs: SimpleNamespace(
    analysis_mode='test-isolated',
    resolved_provider='test',
    sections={},
    trace_ids=[],
    requirements={},
    supplier_questions=[],
    rfq_draft={},
    contract_risks=[],
    bid_decision=None,
)
settings=Settings(database_url='sqlite:///'+sys.argv[1])
result=run_controlled_operator_llm(
    run_id='SYNTHETIC-ORM-TEST',
    notice_text='notice',
    technical_spec_text='spec',
    contract_draft_text='contract',
    quote_paths=[],
    settings_getter=lambda: settings,
)
assert result is not None, 'ORM registration failed in isolated process'
assert result['analysis_mode']=='test-isolated'
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(db_path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-1200:]
    assert db_path.exists()
