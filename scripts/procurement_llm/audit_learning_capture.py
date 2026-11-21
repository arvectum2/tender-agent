"""Read-only compliance audit for saved Tender Agent analyses and learning intake.

No raw reports and no new database. A clean audit does not imply training
quality or complete coverage of external ChatGPT conversations.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import String, cast, create_engine, func, literal, select
from sqlalchemy.orm import Session

from scripts.procurement_llm.import_candidates import _engine_url
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.tender_research.models import TenderAnalysisRun


def audit(session: Session) -> dict:
    obs = ProcurementLearningObservation
    runs = TenderAnalysisRun
    total_saved = session.scalar(select(func.count()).select_from(runs))
    exists_obs = (
        select(obs.observation_id).where(
            obs.event_kind == "analysis_run",
            obs.source_ref == literal("tender_analysis_runs:") + cast(runs.id, String),
        ).exists()
    )
    uncovered = session.scalar(select(func.count()).select_from(runs).where(~exists_obs))
    all_obs = session.scalar(select(func.count()).select_from(obs))
    research = session.scalar(
        select(func.count()).select_from(obs).where(
            obs.source_ref.like("manual:ta-research:%")
        )
    )
    invalid_training = session.scalar(
        select(func.count()).select_from(obs).where(
            obs.training_status != "candidate_unreviewed"
        )
    )
    return {
        "contract_version": "canonical_procurement_capture_readonly_audit_v1",
        "existing_database": "arvectum",
        "saved_tender_agent_analysis_runs": total_saved,
        "saved_runs_missing_candidate_capture": uncovered,
        "saved_runs_with_candidate_capture": total_saved - uncovered,
        "existing_learning_observation_total": all_obs,
        "source_research_intake_observations": research,
        "unexpected_training_status_count": invalid_training,
        "all_saved_analysis_runs_have_learning_capture": uncovered == 0,
        "future_external_chatgpt_coverage_verified": False,
        "human_training_gold_created": False,
        "database_mutations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit 2 if saved run capture incomplete")
    args = parser.parse_args()
    engine = create_engine(_engine_url(), future=True)
    try:
        with Session(engine) as session:
            # SELECTs only; no commits, no file writes, no ad hoc DDL.
            report = audit(session)
            session.rollback()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 2 if args.strict and (
            not report["all_saved_analysis_runs_have_learning_capture"]
            or report["unexpected_training_status_count"]
        ) else 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
