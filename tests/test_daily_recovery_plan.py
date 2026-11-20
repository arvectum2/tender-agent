from dataclasses import replace

import pytest

from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.recovery_plan import RecoveryTarget, plan_target
from src.modules.deal_registry.models import Deal
from src.tender_research.models import ProcurementTender, TenderAnalysisRun

N = "0123456789012345678"
FP = "a" * 64
D = "DL-test"


@pytest.fixture
def scenario(session):
    run = DailyTenderRun(
        run_id="run1",
        profile_id="fixture",
        profile_version="1",
        profile_snapshot_json={},
        status="COMPLETED_WITH_ERRORS",
        current_stage="DONE",
    )
    deal = Deal(
        deal_id=D,
        title="Test",
        procurement_number=N,
        initial_source_type="PORTAL_INGEST",
        direction_type="SERVICE",
        domain_type="test",
        current_status="NEW",
    )
    tender = ProcurementTender(
        source="eis", external_id=N, registry_number=N, law_type="44fz", title="Fixture"
    )
    session.add_all([run, deal, tender])
    session.flush()
    item = DailyTenderRunItem(
        run_id="run1",
        registry_number=N,
        source="public_eis_html_44fz",
        law="44fz",
        title="Fixture",
        source_fingerprint=FP,
        status="FAILED",
        deal_id=D,
    )
    session.add(item)
    session.commit()
    return RecoveryTarget("run1", N, D, FP), item


def test_exact_recovery_candidate(session, scenario):
    target, item = scenario
    plan = plan_target(session, target)
    assert plan["status"] == "candidate_for_reviewed_recovery"
    assert plan["documents"] == plan["chunks"] == 0
    assert item.status == "FAILED"
    assert not session.new and not session.dirty and not session.deleted


def test_identity_binding(session, scenario):
    target, _ = scenario
    assert (
        plan_target(session, replace(target, expected_source_fingerprint="b" * 64))[
            "status"
        ]
        == "identity_mismatch"
    )
    assert (
        plan_target(session, replace(target, expected_deal_id="other"))["status"]
        == "identity_mismatch"
    )
    with pytest.raises(ValueError):
        replace(target, expected_source_fingerprint="aaa")


def test_completed_sibling_is_skipped(session, scenario):
    target, item = scenario
    session.add(
        DailyTenderRun(
            run_id="run2",
            profile_id="fixture",
            profile_version="1",
            profile_snapshot_json={},
            status="WAITING_HUMAN",
            current_stage="WAIT_HUMAN",
        )
    )
    session.flush()
    session.add(
        DailyTenderRunItem(
            run_id="run2",
            registry_number=N,
            source=item.source,
            law=item.law,
            title="fixture",
            source_fingerprint=FP,
            status="MANAGER_READY",
            deal_id=D,
            analysis_run_id="analysis",
            analysis_status="completed",
        )
    )
    session.commit()
    assert plan_target(session, target)["status"] == "already_completed"


def test_orphan_history_blocks_reanalysis(session, scenario):
    target, _ = scenario
    session.add(
        TenderAnalysisRun(registry_number=N, status="completed", used_llm=False)
    )
    session.commit()
    assert plan_target(session, target)["status"] == "unreconciled_analysis_history"


def test_human_or_processing_protected(session, scenario):
    target, item = scenario
    item.human_decision = "GO"
    session.commit()
    assert plan_target(session, target)["status"] == "human_or_active_work_review"
    item.human_decision = None
    item.status = "PROCESSING"
    session.commit()
    assert plan_target(session, target)["status"] == "human_or_active_work_review"
