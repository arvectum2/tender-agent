import hashlib
import json
from dataclasses import replace

import pytest
from sqlalchemy import select

from src.modules.daily_tender_run.analysis_recovery import (
    complete_indexed_analysis,
    profile_for_target,
)
from src.modules.daily_tender_run.manager_synthesis import ManagerSynthesis
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.recovery_plan import RecoveryTarget
from src.modules.daily_tender_run.schemas import DailyTenderProfile
from src.modules.deal_registry.models import Deal
from src.tender_research.models import ProcurementTender, TenderAnalysisRun
from src.tender_research.rag.schemas import TenderAnalysisResult, TenderAnalysisSection

N = "0123456789012345678"


@pytest.fixture
def setup_case(session, tmp_path):
    profile = DailyTenderProfile(
        profile_id="fixture", version="1", queries=["fixture"], analysis_use_llm=True
    )
    session.add_all(
        [
            DailyTenderRun(
                run_id="run1",
                profile_id="fixture",
                profile_version="1",
                profile_snapshot_json=profile.model_dump(mode="json"),
                status="WAITING_HUMAN",
                current_stage="DONE",
                error_summary="discovery gap",
            ),
            Deal(
                deal_id="DL-test",
                title="Fixture",
                procurement_number=N,
                initial_source_type="PORTAL_INGEST",
                direction_type="SERVICE",
                domain_type="test",
                current_status="NEW",
            ),
            ProcurementTender(
                source="eis",
                external_id=N,
                registry_number=N,
                law_type="44fz",
                title="Fixture",
            ),
        ]
    )
    session.flush()
    session.add(
        DailyTenderRunItem(
            run_id="run1",
            registry_number=N,
            source="public_eis_html_44fz",
            law="44fz",
            title="Fixture",
            source_fingerprint="a" * 64,
            status="FAILED",
            deal_id="DL-test",
            stage="INDEX_DATA_PLATFORM",
            error="previous timeout",
        )
    )
    session.commit()
    report = tmp_path / "report.md"
    report.write_text("source-grounded fixture", encoding="utf-8")
    analysis = TenderAnalysisResult(
        status="completed",
        registry_number=N,
        sections=[TenderAnalysisSection("subject", "Subject", "question", "fixture")],
        sections_count=1,
        sources_count=1,
        used_llm=True,
        report_markdown=report.read_text(),
    )
    return {
        "target": RecoveryTarget("run1", N, "DL-test", "a" * 64),
        "analysis": analysis,
        "synthesis": ManagerSynthesis(
            recommendation="NEEDS_REVIEW", rationale="fixture"
        ),
        "report": report,
        "expected_profile": profile,
        "index_identity_sha256": "b" * 64,
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    }


def test_atomic_completion_preserves_original_failure_and_run_gap(session, setup_case):
    result = complete_indexed_analysis(session, **setup_case)
    session.commit()
    history = session.get(TenderAnalysisRun, result["analysis_run_id"])
    item = session.scalars(select(DailyTenderRunItem)).one()
    run = session.scalars(select(DailyTenderRun)).one()
    assert history.id == item.analysis_run_id
    assert item.status == "MANAGER_READY" and item.human_decision is None
    assert (
        json.loads(history.metadata_json)["daily_recovery"]["prior_error"]
        == "previous timeout"
    )
    assert run.counts_json["failed"] == 0 and run.counts_json["deep_analyzed"] == 1
    assert (
        run.digest_json["discovery_incomplete"] and run.error_summary == "discovery gap"
    )
    assert run.digest_json["human_control"]["external_submission_allowed"] is False
    with pytest.raises(ValueError, match="pending recovery"):
        complete_indexed_analysis(session, **setup_case)
    session.rollback()
    assert len(session.scalars(select(TenderAnalysisRun)).all()) == 1


def test_rollback_does_not_keep_orphan_history(session, setup_case):
    complete_indexed_analysis(session, **setup_case)
    session.rollback()
    assert not session.scalars(select(TenderAnalysisRun)).all()
    assert session.scalars(select(DailyTenderRunItem)).one().status == "FAILED"


@pytest.mark.parametrize(
    "defect",
    [
        "bad_report",
        "non_llm",
        "wrong_notice",
        "human_control",
        "wrong_profile",
        "no_sources",
    ],
)
def test_recovery_rejects_incomplete_evidence(session, setup_case, defect):
    args = setup_case.copy()
    if defect == "bad_report":
        args["report"].write_text("changed")
    elif defect == "non_llm":
        args["analysis"] = replace(args["analysis"], used_llm=False)
    elif defect == "wrong_notice":
        args["analysis"] = replace(args["analysis"], registry_number="9" * 19)
    elif defect == "human_control":
        args["synthesis"] = args["synthesis"].model_copy(
            update={"human_control_required": False}
        )
    elif defect == "no_sources":
        args["analysis"] = replace(args["analysis"], sources_count=0)
    else:
        args["expected_profile"] = profile_for_target(
            session, args["target"]
        ).model_copy(update={"analysis_mode": "fast"})
    with pytest.raises(ValueError):
        complete_indexed_analysis(session, **args)
    session.rollback()
    assert not session.scalars(select(TenderAnalysisRun)).all()


def test_report_preservation(tmp_path):
    from scripts.ops.recover_daily_analysis import persist_report

    root = tmp_path.resolve() / "reports"
    first, digest = persist_report(root, N, "test report")
    second, repeated = persist_report(root, N, "test report")
    assert first != second
    assert first.read_bytes() == second.read_bytes() == b"test report"
    assert digest == repeated == hashlib.sha256(b"test report").hexdigest()
    assert first.stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError):
        persist_report(root, "../escape", "report")
    with pytest.raises(ValueError):
        persist_report(root, N, "")
