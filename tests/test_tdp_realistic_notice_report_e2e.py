"""Actual report.json writer golden: matched EIS source beats generic heading."""

from __future__ import annotations

import json

from tests.test_tender_operator_agent_upload_demo import (
    _mock_text_platform,
    _set_runs_root,
)

NUMBER = "0372200172326000015"
OFFICIAL = "Оказание услуг по разработке сайта Музея Хлеба"


def test_official_eis_notice_survives_persisted_operator_report(
    client, monkeypatch, tmp_path
):
    _mock_text_platform(monkeypatch)
    root = _set_runs_root(monkeypatch, tmp_path)
    notice = (
        "<notice><purchaseNumber>" + NUMBER + "</purchaseNumber>"
        "<purchaseObjectInfo>" + OFFICIAL + "</purchaseObjectInfo>"
        "<maxPrice>1000000.00</maxPrice>"
        "<endDT>2026-10-16T10:00:00+03:00</endDT></notice>"
    ).encode()
    created = client.post(
        "/api/demo/tender-agent/runs",
        data={
            "tender_title": "Заглушка ЕИС",
            "tender_category": "Услуги",
            "customer_name": "Заказчик",
        },
        files=[
            ("files", ("notice.xml", notice, "application/xml")),
            ("files", ("technical_spec.txt", "Раздел 1. Общие требования.\nРазработать сайт.".encode(), "text/plain")),
            ("files", ("contract_draft.txt", "Проект контракта. Оплата в течение 7 дней.".encode(), "text/plain")),
        ],
    )
    assert created.status_code == 200
    rid = created.json()["run_id"]
    meta_path = root / rid / "metadata.json"
    metadata = json.loads(meta_path.read_text())
    metadata["procurement_source"] = "zakupki_gov_ru_getdocs_ip"
    metadata["procurement_id"] = NUMBER
    metadata["procurement"] = {
        "procurement_number": NUMBER,
        "title": "Заглушка ЕИС",
        "initial_price": 1000000.0,
    }
    metadata["mode"] = "procurement_search_intake"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False))
    processed = client.post(f"/api/demo/tender-agent/runs/{rid}/analyze")
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] in ("completed_with_warnings", "needs_review", "completed")
    enriched = json.loads(meta_path.read_text())
    assert enriched["_field_evidence"]["procurement_title"] == "eis_notice:procurement_subject"
    report = client.get(f"/api/demo/tender-agent/runs/{rid}/report")
    assert report.status_code == 200
    sections = report.json()["sections"]
    requirement = next(s for s in sections if s["title"] == "Требования")
    assert OFFICIAL in requirement["items"][0]
    assert "eis-xml:" in requirement["items"][0]
    assert not any("Предмет закупки: Раздел 1." in v for v in requirement["items"])
    assert any("НМЦК: 1000000.00" in v for v in requirement["items"])
    assert "Полный LLM-анализ документов не выполнялся" in str(enriched["limitations"])
