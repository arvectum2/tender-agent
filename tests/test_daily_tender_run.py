from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.main import app
from src.modules.daily_tender_run.manager_synthesis import ManagerSynthesis
from src.modules.daily_tender_run.models import DailyTenderRunItem
from src.modules.mobile_api.auth import require_mobile_bearer
from src.modules.tender_intake.models import TenderIntakeRecord
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
        lambda **kwargs: {"cards": [dict(card) for card in cards]},
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
        lambda **kwargs: {"cards": [dict(card)]},
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
