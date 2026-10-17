"""One-off PostgreSQL acceptance on a RESTORED, DISPOSABLE arvectum clone.

Run with PROCUREMENT_CORPUS_ACCEPTANCE_DB_URL set to a named temporary clone.
Never connect this test to a live PostgreSQL database.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from scripts.procurement_llm.import_candidates import _legacy_items
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_analysis_candidate,
)
from src.tender_research.models import TenderAnalysisRun

_LEGACY = "/Volumes/ArvectumSSD/Arvectum/private/procurement-llm/corpus-v1/candidate-registry.sqlite3"


def test_recovered_postgres_snapshot_lossless_and_idempotent():
    url = os.environ.get("PROCUREMENT_CORPUS_ACCEPTANCE_DB_URL")
    if not url:
        pytest.skip("Requires restored, disposable PostgreSQL clone")
    name = make_url(url).database
    if name != "arvectum_learning_acceptance_20261016":
        pytest.fail("REFUSING real database: acceptance test must never target production")
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            initial = session.scalar(select(func.count()).select_from(ProcurementLearningObservation))
            assert initial in (0, 74)
            legacy = _legacy_items(__import__("pathlib").Path(_LEGACY))
            runs = session.scalars(select(TenderAnalysisRun).order_by(TenderAnalysisRun.id)).all()
            assert len(legacy) == 29
            assert len(runs) == 45
            rows = [*legacy, *(make_analysis_candidate(r) for r in runs)]
            added = sum(append_candidate(session, row) for row in rows)
            assert added == (74 if initial == 0 else 0), f'initial={initial} added={added}'
            assert sum(append_candidate(session, row) for row in rows) == 0
            kinds = session.execute(
                select(ProcurementLearningObservation.event_kind,
                       func.count(ProcurementLearningObservation.observation_id))
                .group_by(ProcurementLearningObservation.event_kind)
            ).all()
            assert dict(kinds) == {
                "analysis_run": 45, "development_e2e": 20, "manual_review": 9
            }
            all_rows = session.scalars(select(ProcurementLearningObservation)).all()
            assert len({row.observation_id for row in all_rows}) == 74
            assert all(row.training_status == "candidate_unreviewed" for row in all_rows)
            assert all(row.visibility_scope in ("owner_internal", "tenant") for row in all_rows)
            assert session.execute(select(func.count()).select_from(TenderAnalysisRun)).scalar_one() == 45
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(ProcurementLearningObservation)) == 74
    finally:
        engine.dispose()
