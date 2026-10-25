"""Schema-valid controlled LLM output must be visible but never source-verified."""

from __future__ import annotations

import json

from src.modules.tender_operator_agent_demo.operator_llm_report_projection import (
    candidate_requirement_rows,
    candidate_rfq_sections,
    candidate_risks,
    candidate_supplier_questions,
)
from tests.test_tender_operator_agent_upload_demo import (
    _sample_upload_payload,
    _set_runs_root,
)


def test_llm_candidates_are_human_review_only():
    req = candidate_requirement_rows({
        "technical_requirements": ["Адаптивная вёрстка", "Адаптивная вёрстка"],
        "document_requirements": ["Подтверждение прав на исходники"],
    })
    assert len(req) == 2
    assert all(row["verification_status"] == "unverified" for row in req)
    assert all(row["source"] == "unverified_llm" for row in req)
    risks = candidate_risks([{
        "clause": "Штраф за просрочку",
        "classification": "deal_breaker_candidate",
        "impact": "Затраты на штрафы",
        "mitigation": "Проверить срок",
    }])
    assert len(risks) == 1
    assert risks[0]["classification"] != "deal_breaker_candidate"
    assert risks[0]["evidence_ids"] == ""
    assert risks[0]["source_status"] == "unverified_llm"
    questions = candidate_supplier_questions([{"question": "Есть ли опыт музейных сайтов?"}])
    assert len(questions) == 1 and questions[0].startswith("[LLM")
    draft = candidate_rfq_sections({"intro": "Требуется сайт", "requested_response_items": ["Срок и стоимость"]})
    assert len(draft) == 2 and all(item.startswith("[Черновик LLM") for item in draft)


def test_real_upload_report_persists_visible_unverified_llm_candidates(client, monkeypatch, tmp_path):
    from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy

    run_root = _set_runs_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        legacy, "_try_run_llm_workflow",
        lambda **_kwargs: {
            "analysis_mode": "llm_tender_operator_provider",
            "resolved_provider": "local-openai-compatible",
            "sections": {
                key: {"validation_status": "PASSED"}
                for key in ("requirements", "supplier_questions", "rfq_draft", "contract_risk_memo")
            },
            "trace_ids": [],
            "requirements": {
                "technical_requirements": ["Выполнить адаптивную вёрстку"],
                "document_requirements": ["Передать исходный код"],
                "qualification_requirements": [],
            },
            "supplier_questions": [{"question": "Какой срок сдачи?", "category": "general"}],
            "rfq_draft": {
                "email_subject": "Запрос КП на сайт",
                "intro": "Просим предоставить оценку",
                "requested_response_items": ["Бюджет и сроки"],
            },
            "contract_risks": [{
                "clause": "Штраф за просрочку",
                "classification": "deal_breaker_candidate",
                "impact": "Риск расходов",
                "mitigation": "Проверить договор",
            }],
            "bid_decision": None,
        },
    )
    data, files = _sample_upload_payload(include_quote=False)
    created = client.post("/api/demo/tender-agent/runs", data=data, files=files)
    assert created.status_code == 200
    rid = created.json()["run_id"]
    response = client.post(f"/api/demo/tender-agent/runs/{rid}/analyze")
    assert response.status_code == 200
    assert response.json()["analysis_mode"] == "llm_tender_operator_provider"

    output = run_root / rid / "output"
    requirements = json.loads((output / "requirements.json").read_text())
    assert any(
        item["verification_status"] == "unverified"
        and "Выполнить адаптивную" in item["title"]
        for item in requirements["requirements"]
    )
    risks = json.loads((output / "contract_risks.json").read_text())
    assert any(
        row["source_status"] == "unverified_llm"
        and row["status"] == "requires_review"
        and row["severity"] == "needs_review"
        for row in risks["risks"]
    )
    questions = json.loads((output / "supplier_questions.json").read_text())
    assert any(q.startswith("[LLM") and "Какой срок" in q for q in questions["questions"])
    rfq = json.loads((output / "rfq_draft.json").read_text())
    assert any("Бюджет и сроки" in line for line in rfq["sections"])
