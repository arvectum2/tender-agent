from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.main import app
from src.modules.daily_tender_run.manager_synthesis import ManagerSynthesis
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.profiles import load_daily_tender_profile
from src.modules.event_log.schemas import AppendDecisionRequest
from src.modules.event_log.service import append_decision
from src.modules.mobile_api.auth import require_mobile_bearer
from src.modules.post_submission.models import PostSubmissionTrackerSet
from src.modules.submission_control.models import SubmissionExecutionSet
from src.modules.submission_readiness.models import (
    SubmissionReadinessRecord,
    SubmissionReadinessSet,
)
from src.modules.tender_intake.models import TenderIntakeRecord
from src.shared.enums import DecisionByType
from src.tender_research.rag.schemas import TenderAnalysisResult, TenderAnalysisSection


def _search_card(registry_number: str = "0123456789012345678") -> dict:
    return {
        "registry_number": registry_number,
        "source": "public_eis_html_44fz",
        "source_url": (
            "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
            f"?regNumber={registry_number}"
        ),
        "title": "Оказание услуг по разработке программного обеспечения",
        "customer_name": "Тестовый заказчик",
        "initial_price": 1_250_000.0,
        "deadline": "31.12.2026 18:00",
        "publication_date": "06.10.2026",
        "status": "Подача заявок",
    }


def _install_happy_path(monkeypatch, *, registry_number: str = "0123456789012345678"):
    from src.modules.daily_tender_run import service

    card = _search_card(registry_number)
    monkeypatch.setattr(
        service,
        "search_public_44fz",
        lambda **kwargs: {"cards": [dict(card)], "outcome": "success_with_results"},
    )
    monkeypatch.setattr(
        service.TenderResearchPipeline,
        "ingest_public_by_registry_number",
        lambda self, registry_number: (SimpleNamespace(id="research-tender"), {}),
    )
    monkeypatch.setattr(
        service,
        "prepare_tender_for_analysis",
        lambda **kwargs: SimpleNamespace(
            ready_for_analysis=True,
            errors=[],
            warnings=[],
        ),
    )

    analyze = Mock(
        return_value=TenderAnalysisResult(
            status="completed",
            registry_number=registry_number,
            sections=[
                TenderAnalysisSection(
                    id="subject",
                    title="Предмет закупки",
                    question="Что требуется?",
                    answer="Требуется разработка программного обеспечения.",
                    sources=[],
                )
            ],
            sections_count=1,
            sources_count=1,
            analysis_mode="balanced",
            report_markdown="# report",
            report_path="/tmp/dtr-report.md",
            used_llm=True,
            llm_model="local-test",
            retrieval_provider="data_platform",
            retrieval_model="hybrid",
            run_id="ANALYSIS-DTR-001",
        )
    )
    monkeypatch.setattr(service, "analyze_tender", analyze)
    monkeypatch.setattr(
        service,
        "synthesize_manager_brief",
        lambda *args, **kwargs: ManagerSynthesis(
            recommendation="GO",
            confidence="high",
            rationale="Требования понятны, явных блокеров в анализе не выявлено.",
            strongest_reasons=["Профиль работ соответствует IT-разработке"],
            blockers=[],
            unknowns=[],
            application_requirements=["Подготовить состав заявки"],
            execution_risks=["Проверить доступы к контуру заказчика"],
            onsite_required=False,
            next_actions=["Руководителю принять решение GO/NO GO/DEFER"],
            human_control_required=True,
        ),
    )
    return analyze





def test_v2_screen_matches_manual_arvectum_selection_shapes():
    from datetime import UTC, datetime

    from src.modules.daily_tender_run.profiles import load_daily_tender_profile
    from src.modules.daily_tender_run.service import _screen_card

    profile = load_daily_tender_profile("arvectum-it")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

    cases = [
        (
            "Разработка сайта на платформе Tilda",
            152_033.33,
            "IN",
            None,
        ),
        (
            "Разработка GIS-плагина для Axioma 7.x",
            521_000,
            "IN",
            None,
        ),
        (
            "Доработка программного обеспечения сервера и автоматизированной информационной системы в части разработки дополнительной подсистемы",
            2_500_000,
            "IN",
            None,
        ),
        (
            "Доработка государственной информационной системы GeoPrime",
            3_475_918,
            "IN",
            None,
        ),
        (
            "Сопровождение систем информационного обеспечения деятельности: Консультант плюс",
            350_000,
            "OUT",
            "support_only_without_custom_development",
        ),
        (
            "Поставка оборудования, передача неисключительных прав на использование программного обеспечения, сертификатов технической поддержки и выполнение работ в целях модернизации программно-аппаратных комплексов",
            568_351_039.94,
            "OUT",
            "license_or_hardware_supply_without_custom_development",
        ),
        (
            "Оказание услуг по установке, настройке СКЗИ ViPNet и предоставлению сертификатов технической поддержки",
            1_199_100,
            "OUT",
            "license_or_hardware_supply_without_custom_development",
        ),
    ]

    for title, nmck, expected_status, expected_reason in cases:
        status, _score, reasons = _screen_card(
            profile,
            {
                "title": title,
                "customer_name": "Заказчик",
                "initial_price": nmck,
                "deadline": "20.10.2026 18:00",
                "status": "Подача заявок",
            },
            now=now,
        )
        assert status == expected_status, (title, reasons)
        if expected_reason:
            assert expected_reason in reasons


def test_v2_screen_hard_caps_obviously_out_of_scale_enterprise_contracts():
    from datetime import UTC, datetime

    from src.modules.daily_tender_run.profiles import load_daily_tender_profile
    from src.modules.daily_tender_run.service import _screen_card

    profile = load_daily_tender_profile("arvectum-it")
    status, _score, reasons = _screen_card(
        profile,
        {
            "title": "Модернизация информационной системы и развитие пользовательских сервисов",
            "customer_name": "Центр развития цифровых технологий",
            "initial_price": 143_864_502.27,
            "deadline": "20.10.2026 18:00",
            "status": "Подача заявок",
        },
        now=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
    )

    assert status == "OUT"
    assert reasons == ["nmck_above_profile_maximum"]


def test_v2_screen_does_not_use_customer_name_as_relevance_signal():
    from datetime import UTC, datetime

    from src.modules.daily_tender_run.profiles import load_daily_tender_profile
    from src.modules.daily_tender_run.service import _screen_card

    profile = load_daily_tender_profile("arvectum-it")
    status, _score, reasons = _screen_card(
        profile,
        {
            "title": "Оказание консультационных услуг",
            "customer_name": "Центр развития информационных технологий",
            "initial_price": 1_000_000,
            "deadline": "20.10.2026 18:00",
            "status": "Подача заявок",
        },
        now=datetime(2026, 10, 6, 12, 0, tzinfo=UTC),
    )

    assert status == "OUT"
    assert reasons == ["no_profile_keyword_match"]

def test_screen_enforces_deep_analysis_cap_with_autoflush_disabled_and_resume_state(
    session,
):
    from src.modules.daily_tender_run import service
    from src.modules.daily_tender_run.schemas import DailyTenderProfile

    profile = DailyTenderProfile(
        profile_id="cap-test",
        version="1",
        queries=["программное обеспечение"],
        max_deep_analysis=3,
        include_keywords=["программ"],
        exclude_keywords=[],
        require_include_keyword=True,
        analysis_use_llm=False,
        synthesis_use_llm=False,
    )
    run = DailyTenderRun(
        run_id="DTR-CAP-TEST",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_snapshot_json=profile.model_dump(mode="json"),
        status="RUNNING",
        current_stage="SCREEN",
        counts_json={},
    )
    session.add(run)
    session.commit()

    processing = DailyTenderRunItem(
        run_id=run.run_id,
        registry_number="1000000000000000000",
        law="44fz",
        source="test",
        title="Разработка программного обеспечения",
        source_fingerprint="processing",
        query_hits_json=["q"],
        stage="INDEX_DATA_PLATFORM",
        status="PROCESSING",
        screening_status="IN",
        screening_score=100.0,
        screening_reasons_json=["already_processing"],
    )
    session.add(processing)

    for idx in range(5):
        session.add(
            DailyTenderRunItem(
                run_id=run.run_id,
                registry_number=f"200000000000000000{idx}",
                law="44fz",
                source="test",
                title=f"Разработка программного обеспечения {idx}",
                source_fingerprint=f"discovered-{idx}",
                query_hits_json=["q"],
                stage="DISCOVER",
                status="DISCOVERED",
                screening_reasons_json=[],
            )
        )
    session.commit()

    service._screen(session, run, profile)

    items = list(
        session.query(DailyTenderRunItem)
        .filter(DailyTenderRunItem.run_id == run.run_id)
        .all()
    )
    assert sum(item.status == "PROCESSING" for item in items) == 1
    assert sum(item.status == "SHORTLISTED" for item in items) == 2
    screened_out = [item for item in items if item.status == "SCREENED_OUT"]
    assert len(screened_out) == 3
    assert all(
        "daily_deep_analysis_limit" in item.screening_reasons_json
        for item in screened_out
    )


def test_daily_tender_run_builds_manager_ready_case_and_mobile_projection(
    client,
    session,
    monkeypatch,
):
    analyze = _install_happy_path(monkeypatch)

    response = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "WAITING_HUMAN"
    assert body["current_stage"] == "WAIT_HUMAN"
    assert body["counts"]["discovered"] == 1
    assert body["counts"]["deep_analyzed"] == 1
    assert body["counts"]["needs_manager"] == 1
    assert body["counts"]["agent_go"] == 1
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["status"] == "MANAGER_READY"
    assert item["agent_recommendation"] == "GO"
    assert item["analysis_run_id"] == "ANALYSIS-DTR-001"
    assert item["deal_id"]
    assert analyze.call_count == 1
    assert analyze.call_args.kwargs["history_source"] == "daily_tender_run"
    assert session.query(TenderIntakeRecord).count() == 1

    app.dependency_overrides[require_mobile_bearer] = lambda: "device-dtr-001"
    mobile = client.get("/mobile/v1/inbox")
    assert mobile.status_code == 200
    mobile_item = mobile.json()["items"][0]
    assert mobile_item["deal_id"] == item["deal_id"]
    assert mobile_item["nmck_rub"] == 1_250_000.0
    assert mobile_item["deadline_at"] is not None
    assert mobile_item["recommendation"] == "GO"
    assert mobile_item["recommendation_confidence"] == "high"
    assert mobile_item["recommendation_reasons"] == [
        "Профиль работ соответствует IT-разработке"
    ]
    assert mobile_item["analysis_run_id"] == "ANALYSIS-DTR-001"

    digest = client.get("/mobile/v1/digest/latest")
    assert digest.status_code == 200
    assert digest.json()["run_id"] == body["run_id"]
    assert digest.json()["counts"]["needs_manager"] == 1
    assert digest.json()["human_control"]["external_submission_allowed"] is False

    decision = client.post(
        f"/mobile/v1/procurements/{item['deal_id']}/decision",
        json={
            "action": "GO",
            "rationale": "Подтверждено руководителем",
            "reason_codes": ["OWNER_GO"],
            "idempotency_key": "dtr-owner-go-0001",
        },
    )
    assert decision.status_code == 200
    digest_after_decision = client.get("/mobile/v1/digest/latest")
    assert digest_after_decision.status_code == 200
    assert digest_after_decision.json()["actionable"] == []
    assert digest_after_decision.json()["counts"]["needs_manager"] == 0


def test_daily_tender_run_deduplicates_unchanged_procurement_across_runs(
    client,
    session,
    monkeypatch,
):
    analyze = _install_happy_path(monkeypatch)

    first = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )
    assert first.status_code == 201
    assert first.json()["counts"]["deep_analyzed"] == 1

    second = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["status"] == "COMPLETED"
    assert second_body["counts"]["duplicates"] == 1
    assert second_body["counts"]["deep_analyzed"] == 0
    assert second_body["counts"]["needs_manager"] == 0
    assert second_body["items"][0]["status"] == "DUPLICATE"
    assert analyze.call_count == 1
    assert session.query(TenderIntakeRecord).count() == 1
    assert session.query(DailyTenderRunItem).count() == 2


def test_daily_tender_run_item_failure_isolated_from_other_procurements(
    client,
    monkeypatch,
):
    from src.modules.daily_tender_run import service

    cards = [_search_card("0123456789012345678"), _search_card("0123456789012345679")]
    monkeypatch.setattr(
        service,
        "search_public_44fz",
        lambda **kwargs: {"cards": [dict(card) for card in cards], "outcome": "success_with_results"},
    )
    monkeypatch.setattr(
        service.TenderResearchPipeline,
        "ingest_public_by_registry_number",
        lambda self, registry_number: (SimpleNamespace(id=registry_number), {}),
    )

    def prepare(*, registry_number: str, **kwargs):
        return SimpleNamespace(
            ready_for_analysis=registry_number.endswith("8"),
            errors=[] if registry_number.endswith("8") else ["document_set_incomplete"],
            warnings=[],
        )

    monkeypatch.setattr(service, "prepare_tender_for_analysis", prepare)
    monkeypatch.setattr(
        service,
        "analyze_tender",
        lambda registry_number, **kwargs: TenderAnalysisResult(
            status="completed",
            registry_number=registry_number,
            sections=[],
            sections_count=0,
            sources_count=1,
            analysis_mode="balanced",
            report_path=f"/tmp/{registry_number}.md",
            run_id=f"AN-{registry_number}",
        ),
    )
    monkeypatch.setattr(
        service,
        "synthesize_manager_brief",
        lambda *args, **kwargs: ManagerSynthesis(
            recommendation="NEEDS_REVIEW",
            confidence="medium",
            rationale="Нужна проверка руководителя.",
            strongest_reasons=[],
            blockers=[],
            unknowns=["commercial_economics"],
            next_actions=["Проверить экономику"],
        ),
    )

    response = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["counts"]["discovered"] == 2
    assert body["counts"]["deep_analyzed"] == 1
    assert body["counts"]["failed"] == 1
    assert body["status"] == "WAITING_HUMAN"
    assert body["current_stage"] == "WAIT_HUMAN"
    statuses = {item["registry_number"]: item["status"] for item in body["items"]}
    assert statuses["0123456789012345678"] == "MANAGER_READY"
    assert statuses["0123456789012345679"] == "FAILED"



def test_daily_tender_run_all_failures_complete_with_errors_and_retry(
    client,
    monkeypatch,
):
    from src.modules.daily_tender_run import service

    registry_number = "0123456789012345680"
    card = _search_card(registry_number)
    monkeypatch.setattr(
        service,
        "search_public_44fz",
        lambda **kwargs: {"cards": [dict(card)], "outcome": "success_with_results"},
    )
    monkeypatch.setattr(
        service.TenderResearchPipeline,
        "ingest_public_by_registry_number",
        lambda self, registry_number: (SimpleNamespace(id=registry_number), {}),
    )
    state = {"ready": False}

    def prepare(**kwargs):
        return SimpleNamespace(
            ready_for_analysis=state["ready"],
            errors=[] if state["ready"] else ["temporary_document_failure"],
            warnings=[],
        )

    monkeypatch.setattr(service, "prepare_tender_for_analysis", prepare)
    monkeypatch.setattr(
        service,
        "analyze_tender",
        lambda registry_number, **kwargs: TenderAnalysisResult(
            status="completed",
            registry_number=registry_number,
            sections=[],
            sections_count=0,
            sources_count=1,
            analysis_mode="balanced",
            report_path=f"/tmp/{registry_number}.md",
            run_id=f"AN-{registry_number}",
        ),
    )
    monkeypatch.setattr(
        service,
        "synthesize_manager_brief",
        lambda *args, **kwargs: ManagerSynthesis(
            recommendation="NEEDS_REVIEW",
            confidence="medium",
            rationale="Нужна проверка руководителя.",
            unknowns=["commercial_economics"],
        ),
    )

    created = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "COMPLETED_WITH_ERRORS"
    assert body["current_stage"] == "DONE"
    assert body["counts"]["failed"] == 1

    state["ready"] = True
    resumed = client.post(
        f"/api/daily-tender-runs/{body['run_id']}/resume?retry_failed=true"
    )
    assert resumed.status_code == 200
    resumed_body = resumed.json()
    assert resumed_body["status"] == "WAITING_HUMAN"
    assert resumed_body["counts"]["failed"] == 0
    assert resumed_body["counts"]["needs_manager"] == 1
    assert resumed_body["items"][0]["status"] == "MANAGER_READY"



def test_dtr_original_source_timeout_never_persists_signed_url(client, session, monkeypatch):
    from src.modules.daily_tender_run import service

    registry_number = "0128200000126007558"
    secret = "sensitive-eis-archive-token-should-never-leak"
    monkeypatch.setattr(
        service,
        "search_public_44fz",
        lambda **kwargs: {
            "cards": [_search_card(registry_number)],
            "outcome": "success_with_results",
        },
    )

    def source_failure(self, number):
        raise TimeoutError(
            "official source expired: https://int.zakupki.gov.ru/archive.zip?token="
            + secret
        )

    monkeypatch.setattr(
        service.TenderResearchPipeline, "ingest_public_by_registry_number", source_failure
    )
    response = client.post(
        "/api/daily-tender-runs",
        json={"profile_id": "arvectum-it", "run_now": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["counts"]["failed"] == 1
    assert body["status"] == "COMPLETED_WITH_ERRORS"
    assert body["items"][0]["error"] == "source_acquisition_failed:timeout"
    assert secret not in str(body)
    stored = session.query(DailyTenderRunItem).filter_by(run_id=body["run_id"]).one()
    assert stored.error == "source_acquisition_failed:timeout"
    assert secret not in stored.error


def test_dtr_safe_processing_error_never_uses_untrusted_text():
    from src.modules.daily_tender_run.service import _safe_processing_error

    secret = "?X-Amz-Signature=must-not-be-persisted"
    assert (
        _safe_processing_error("INDEX_DATA_PLATFORM", RuntimeError(secret))
        == "source_or_index_not_ready:failure"
    )
    assert (
        _safe_processing_error("ANALYZE", ValueError(secret))
        == "analysis_failed:invalid_input"
    )
    assert (
        _safe_processing_error("SUMMARIZE", ConnectionError(secret))
        == "manager_summary_failed:connection_unavailable"
    )
    assert secret not in _safe_processing_error("unknown", OSError(secret))


def _create_post_go_run(
    session,
    *,
    deal_id: str,
    registry_number: str,
) -> tuple[DailyTenderRun, DailyTenderRunItem]:
    profile = load_daily_tender_profile("arvectum-it")
    run = DailyTenderRun(
        run_id=f"DTR-POST-GO-{registry_number[-6:]}",
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_snapshot_json=profile.model_dump(mode="json"),
        status="WAITING_HUMAN",
        current_stage="WAIT_HUMAN",
        counts_json={},
    )
    item = DailyTenderRunItem(
        run_id=run.run_id,
        registry_number=registry_number,
        law="44fz",
        source="test",
        title=f"Post-GO test {registry_number}",
        customer_name="Тестовый заказчик",
        source_fingerprint=f"fingerprint-{registry_number}",
        query_hits_json=["test"],
        stage="WAIT_HUMAN",
        status="MANAGER_READY",
        screening_status="IN",
        screening_score=100.0,
        screening_reasons_json=["test"],
        deal_id=deal_id,
        analysis_run_id=f"AN-{registry_number}",
        analysis_status="completed",
        strongest_reasons_json=[],
        blockers_json=[],
        unknowns_json=[],
    )
    session.add(run)
    session.add(item)
    session.commit()
    session.refresh(run)
    session.refresh(item)
    return run, item


def _record_dtr_human_decision(
    session,
    *,
    deal_id: str,
    action: str,
    suffix: str,
    deferred_until: str | None = None,
):
    canonical_decision = "NEEDS_REVIEW" if action == "DEFER" else action
    return append_decision(
        session,
        AppendDecisionRequest(
            deal_id=deal_id,
            decision_code="PORTFOLIO_BID_DECISION",
            decided_by_type=DecisionByType.HUMAN,
            decided_by_ref="ios:test-device",
            rationale=f"Human {action}",
            payload_json={
                "decision": canonical_decision,
                "mobile_action": action,
                "reason_codes": [f"TEST_{action}"],
                "deferred_until": deferred_until,
                "source": "tender_agent_ios",
                "idempotency_key": f"dtr3-{suffix}",
            },
        ),
    )


def test_dtr3_go_without_readiness_prerequisites_fails_closed(
    client,
    session,
):
    created = client.post(
        "/procurement-portfolio",
        json={
            "procurement_number": "0999999999999999001",
            "title": "DTR-3 readiness gate",
            "customer_name": "Тестовый заказчик",
            "source_url": None,
            "direction_type": "SERVICE",
            "domain_type": "IT_SOFTWARE_SERVICES",
        },
    )
    assert created.status_code == 201
    deal_id = created.json()["deal_id"]
    run, _item = _create_post_go_run(
        session,
        deal_id=deal_id,
        registry_number="0999999999999999001",
    )
    _record_dtr_human_decision(
        session,
        deal_id=deal_id,
        action="GO",
        suffix="blocked",
    )

    resumed = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert resumed.status_code == 200
    body = resumed.json()
    assert body["status"] == "WAITING_READINESS"
    assert body["current_stage"] == "POST_DECISION"
    item = body["items"][0]
    assert item["human_decision"] == "GO"
    assert item["status"] == "READINESS_BLOCKED"
    assert item["post_decision"]["readiness"]["status"] == "BLOCKED"
    assert set(item["post_decision"]["readiness"]["missing"]) == {
        "bid_completeness",
        "ceo_approval",
        "finance_memo",
        "integrated_risk_memo",
    }
    assert (
        session.query(SubmissionExecutionSet).filter_by(deal_id=deal_id).count()
        == 0
    )


def test_dtr3_human_no_go_stops_without_submission_artifacts(
    client,
    session,
):
    created = client.post(
        "/procurement-portfolio",
        json={
            "procurement_number": "0999999999999999002",
            "title": "DTR-3 NO GO",
            "customer_name": "Тестовый заказчик",
            "source_url": None,
            "direction_type": "SERVICE",
            "domain_type": "IT_SOFTWARE_SERVICES",
        },
    )
    assert created.status_code == 201
    deal_id = created.json()["deal_id"]
    run, _item = _create_post_go_run(
        session,
        deal_id=deal_id,
        registry_number="0999999999999999002",
    )
    _record_dtr_human_decision(
        session,
        deal_id=deal_id,
        action="NO_GO",
        suffix="no-go",
    )

    resumed = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert resumed.status_code == 200
    body = resumed.json()
    assert body["status"] == "COMPLETED"
    item = body["items"][0]
    assert item["stage"] == "DONE"
    assert item["status"] == "DECIDED_NO_GO"
    assert item["human_decision"] == "NO_GO"
    assert item["post_decision"]["post_decision"]["reason"] == "human_no_go"
    assert (
        session.query(SubmissionExecutionSet).filter_by(deal_id=deal_id).count()
        == 0
    )


def test_dtr3_post_go_tracks_only_verified_submission_and_grounded_outcome(
    client,
    session,
):
    from src.modules.bid_packages.models import BidPackageItem, BidPackageRecord
    from tests.test_sprint5b_integration import _prepare_submission_prerequisites

    package = _prepare_submission_prerequisites(client)
    deal_id = package["intake"]["deal_id"]

    readiness_set = session.query(SubmissionReadinessSet).filter_by(
        submission_readiness_set_id=package["readiness"][
            "submission_readiness_set_id"
        ]
    ).one()
    readiness_record = session.query(SubmissionReadinessRecord).filter_by(
        submission_readiness_set_id=readiness_set.submission_readiness_set_id
    ).order_by(SubmissionReadinessRecord.created_at.desc()).first()
    readiness_set.readiness_status = "READY"
    readiness_record.recommendation = "READY"
    session.add(readiness_set)
    session.add(readiness_record)
    session.commit()

    run, _item = _create_post_go_run(
        session,
        deal_id=deal_id,
        registry_number="0999999999999999003",
    )
    _record_dtr_human_decision(
        session,
        deal_id=deal_id,
        action="GO",
        suffix="verified-flow",
    )

    first = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["status"] == "WAITING_SUBMISSION"
    first_item = first_body["items"][0]
    assert first_item["status"] == "AWAITING_SUBMISSION_EVIDENCE"
    execution_set_id = first_item["post_decision"]["submission"][
        "submission_execution_set_id"
    ]
    execution_sets_before = (
        session.query(SubmissionExecutionSet).filter_by(deal_id=deal_id).count()
    )
    assert execution_sets_before == 1

    execution = client.post(
        "/submission-control/start",
        json={
            "submission_execution_set_id": execution_set_id,
            "channel_type": "MANUAL",
        },
    )
    assert execution.status_code == 201
    execution_id = execution.json()["submission_execution_id"]
    submitted = client.post(
        "/submission-control/attempts",
        json={
            "submission_execution_id": execution_id,
            "attempt_no": 1,
            "attempt_status": "SUCCEEDED",
            "notes": "Submitted state without attributable human actor.",
        },
    )
    assert submitted.status_code == 201

    unverified = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert unverified.status_code == 200
    unverified_item = unverified.json()["items"][0]
    assert unverified.json()["status"] == "WAITING_SUBMISSION"
    assert unverified_item["status"] == "AWAITING_SUBMISSION_EVIDENCE"
    assert (
        unverified_item["post_decision"]["submission"]["evidence_status"]
        == "UNVERIFIED"
    )
    assert (
        session.query(PostSubmissionTrackerSet).filter_by(deal_id=deal_id).count()
        == 0
    )

    package_record = session.query(BidPackageRecord).filter_by(
        bid_package_set_id=package["bid_package"]["bid_package_set_id"]
    ).one()
    artifact_ref = session.query(BidPackageItem).filter_by(
        bid_package_id=package_record.bid_package_id
    ).first().artifact_ref
    receipt = client.post(
        "/submission-receipts/register",
        json={
            "deal_id": deal_id,
            "submission_execution_set_id": execution_set_id,
            "receipt_number": "DTR3-RECEIPT-001",
            "receipt_timestamp": "2026-10-07T07:00:00Z",
            "receipt_source": "PORTAL",
            "bindings": [
                {
                    "artifact_ref": artifact_ref,
                    "binding_type": "SCREENSHOT",
                }
            ],
        },
    )
    assert receipt.status_code == 201

    tracked = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert tracked.status_code == 200
    tracked_body = tracked.json()
    assert tracked_body["status"] == "WAITING_OUTCOME"
    tracked_item = tracked_body["items"][0]
    assert tracked_item["status"] == "AWAITING_OUTCOME_EVIDENCE"
    assert (
        tracked_item["post_decision"]["submission"]["evidence"]["kind"]
        == "source_bound_receipt"
    )
    tracker_id = tracked_item["post_decision"]["submission"][
        "post_submission_tracker_set_id"
    ]
    trackers_before = (
        session.query(PostSubmissionTrackerSet).filter_by(deal_id=deal_id).count()
    )
    assert trackers_before == 1

    ungrounded_outcome = client.post(
        "/outcome-intake/register",
        json={
            "deal_id": deal_id,
            "post_submission_tracker_set_id": tracker_id,
            "outcome_code": "WON",
            "effective_at": "2026-10-07T07:10:00Z",
            "rationale": "Unbound outcome must not advance DTR.",
            "bindings": [],
        },
    )
    assert ungrounded_outcome.status_code == 201
    still_waiting = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert still_waiting.status_code == 200
    assert still_waiting.json()["status"] == "WAITING_OUTCOME"
    assert (
        still_waiting.json()["items"][0]["status"]
        == "AWAITING_OUTCOME_EVIDENCE"
    )

    grounded_outcome = client.post(
        "/outcome-intake/register",
        json={
            "deal_id": deal_id,
            "post_submission_tracker_set_id": tracker_id,
            "outcome_code": "WON",
            "effective_at": "2026-10-07T07:20:00Z",
            "rationale": "Published outcome protocol is bound to evidence.",
            "bindings": [
                {
                    "artifact_ref": artifact_ref,
                    "binding_type": "PROTOCOL",
                }
            ],
        },
    )
    assert grounded_outcome.status_code == 201

    completed = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert completed.status_code == 200
    completed_body = completed.json()
    assert completed_body["status"] == "COMPLETED"
    completed_item = completed_body["items"][0]
    assert completed_item["status"] == "OUTCOME_RECORDED"
    assert completed_item["stage"] == "DONE"
    assert completed_item["post_decision"]["outcome"]["code"] == "WON"
    assert completed_body["counts"]["outcome_recorded"] == 1

    idempotent = client.post(f"/api/daily-tender-runs/{run.run_id}/resume")
    assert idempotent.status_code == 200
    assert idempotent.json()["status"] == "COMPLETED"
    assert (
        session.query(SubmissionExecutionSet).filter_by(deal_id=deal_id).count()
        == execution_sets_before
    )
    assert (
        session.query(PostSubmissionTrackerSet).filter_by(deal_id=deal_id).count()
        == trackers_before
    )


def test_dtr_source_error_is_not_successful_empty_and_retries_same_window(client, monkeypatch):
    from src.modules.daily_tender_run import service

    search = Mock(return_value={"cards": [], "outcome": "source_unavailable"})
    monkeypatch.setattr(service, "search_public_44fz", search)
    created = client.post("/api/daily-tender-runs", json={"run_now": True}).json()
    assert created["status"] == "COMPLETED_WITH_ERRORS"
    assert created["counts"]["discovery_incomplete"] == 1
    assert created["digest"]["discovery_incomplete"] is True
    assert created["error_summary"]
    app.dependency_overrides[require_mobile_bearer] = lambda: "device-dtr-discovery"
    digest = client.get("/mobile/v1/digest/latest").json()
    assert digest["run_status"] == "COMPLETED_WITH_ERRORS"
    assert digest["discovery_incomplete"] is True
    window = (search.call_args.kwargs["date_from"], search.call_args.kwargs["date_to"])
    search.return_value = {"cards": [], "outcome": "success_empty"}
    resumed = client.post(f"/api/daily-tender-runs/{created['run_id']}/resume?retry_failed=true").json()
    assert resumed["status"] == "COMPLETED"
    assert resumed["counts"]["discovery_incomplete"] == 0
    assert resumed["error_summary"] is None
    assert (search.call_args.kwargs["date_from"], search.call_args.kwargs["date_to"]) == window


def test_dtr_recovery_includes_pending_and_interrupted_runs(session, monkeypatch):
    from src.modules.daily_tender_run import service
    from src.modules.daily_tender_run.schemas import StartDailyTenderRunRequest

    search = Mock(return_value={"cards": [], "outcome": "success_empty"})
    monkeypatch.setattr(service, "search_public_44fz", search)
    pending = service.create_daily_tender_run(session, StartDailyTenderRunRequest(run_now=False))
    interrupted = service.create_daily_tender_run(session, StartDailyTenderRunRequest(run_now=False))
    interrupted.status = "RUNNING"
    session.commit()
    resumed = service.resume_pending_daily_tender_runs(session, profile_id="arvectum-it")
    assert {r.run_id for r in resumed} == {pending.run_id, interrupted.run_id}
    assert all(r.status == "COMPLETED" for r in resumed)
    assert search.call_count == 2 * len(load_daily_tender_profile("arvectum-it").queries)


def test_dtr_same_run_execution_guard_rejects_overlap_and_releases(session, monkeypatch):
    import pytest

    from src.modules.daily_tender_run import service
    from src.modules.daily_tender_run.schemas import StartDailyTenderRunRequest
    from src.shared.errors import ConflictError

    monkeypatch.setattr(service, "search_public_44fz", lambda **kw: {"cards": [], "outcome": "success_empty"})
    run = service.create_daily_tender_run(session, StartDailyTenderRunRequest(run_now=False))
    with service._run_execution_guard(session, run.run_id), pytest.raises(ConflictError):
        service.execute_daily_tender_run(session, run.run_id)
    assert service.execute_daily_tender_run(session, run.run_id).status == "COMPLETED"


def test_dtr_profile_revision_change_invalidates_unchanged_card_reuse(client, monkeypatch):
    from src.modules.daily_tender_run import service

    analyze = _install_happy_path(monkeypatch)
    first = client.post("/api/daily-tender-runs", json={"run_now": True}).json()
    assert first["counts"]["deep_analyzed"] == 1
    profile = load_daily_tender_profile("arvectum-it").model_copy(update={"version": "test-new-version"})
    monkeypatch.setattr(service, "load_daily_tender_profile", lambda _: profile)
    second = client.post("/api/daily-tender-runs", json={"run_now": True}).json()
    assert second["counts"]["duplicates"] == 0
    assert second["counts"]["deep_analyzed"] == 1
    assert analyze.call_count == 2


def test_dtr_invalid_profile_and_runtime_packaging(client):
    from pathlib import Path

    response = client.post("/api/daily-tender-runs", json={"profile_id": "../arvectum-it"})
    assert response.status_code == 422
    root = Path(__file__).resolve().parents[1]
    for dockerfile in ("Dockerfile", "deploy/local/Dockerfile", "deploy/pilot/Dockerfile"):
        assert "COPY " in (root / dockerfile).read_text()
        assert "config/daily_tender_profiles" in (root / dockerfile).read_text()


def test_dtr_partial_discovery_failure_keeps_ready_items_and_retry_does_not_reanalyze(client, monkeypatch):
    from src.modules.daily_tender_run import service

    analyze = _install_happy_path(monkeypatch)
    profile = load_daily_tender_profile("arvectum-it").model_copy(update={"queries": ["good", "failed"]})
    monkeypatch.setattr(service, "load_daily_tender_profile", lambda _: profile)
    state = {"failed": True}

    def search(**kwargs):
        if kwargs["query"] == "failed" and state["failed"]:
            return {"cards": [], "outcome": "source_error"}
        return {"cards": [_search_card()], "outcome": "success_with_results"}

    monkeypatch.setattr(service, "search_public_44fz", search)
    created = client.post("/api/daily-tender-runs", json={"run_now": True}).json()
    assert created["status"] == "WAITING_HUMAN"
    assert created["counts"]["needs_manager"] == 1
    assert created["counts"]["discovery_incomplete"] == 1
    state["failed"] = False
    resumed = client.post(f"/api/daily-tender-runs/{created['run_id']}/resume?retry_failed=true").json()
    assert resumed["counts"]["discovery_incomplete"] == 0
    assert resumed["items"][0]["query_hits"] == ["good", "failed"]
    assert analyze.call_count == 1


def test_mobile_digest_distinguishes_pending_run_from_no_run(client):
    app.dependency_overrides[require_mobile_bearer] = lambda: "device-dtr-pending"
    empty = client.get("/mobile/v1/digest/latest").json()
    assert empty["run_id"] is None
    assert empty["discovery_incomplete"] is None
    pending = client.post("/api/daily-tender-runs", json={"run_now": False}).json()
    digest = client.get("/mobile/v1/digest/latest").json()
    assert digest["run_id"] == pending["run_id"]
    assert digest["run_status"] == "PENDING"
    assert digest["current_stage"] == "DISCOVER"
    assert digest["discovery_incomplete"] is None
