"""Real EIS fact precedence vs legacy heuristic and no fake source citations."""

from __future__ import annotations

from src.modules.tender_operator_agent_demo.operator_report_assembly import (
    add_verified_notice_to_report_steps,
)
from src.modules.tender_operator_agent_demo.schemas import (
    DemoDetailSection,
    DemoStep,
    DemoStepStatus,
)

NUMBER = "0372200172326000015"
SUBJECT = "Оказание услуг по разработке сайта Музея Хлеба"
FILE = "epNotificationEZK2020_0372200172326000015.xml"


def metadata(source="zakupki_gov_ru_getdocs_ip"):
    return {
        "procurement_source": source,
        "procurement_id": NUMBER,
        "files": [{
            "file_id": "FILE-01", "display_name": FILE, "extension": ".xml",
        }],
        "_verified_notice_facts": {
            "registry_number": NUMBER,
            "file_id": "FILE-01",
            "document": FILE,
            "values": {
                "procurement_title": SUBJECT,
                "application_deadline": "2026-10-16T10:00:00+03:00",
                "nmck": "1000000.00",
            },
        },
    }


def requirements_step():
    return DemoStep(
        key="requirements",
        order=2,
        title="Требования",
        short_title="Требования",
        status=DemoStepStatus.PARTIAL,
        description="ТЗ",
        agent_action="Извлечение",
        result_summary="Предмет закупки: Раздел 1. Общие требования.",
        findings=[
            "Предмет закупки: Раздел 1. Общие требования.",
            "Оплата: 7 рабочих дней с подписания акта.",
        ],
        human_review=["Проверить ТЗ"],
        trace="Режим fallback",
        result_sections=[
            DemoDetailSection(
                title="Предварительный анализ",
                kind="bullets",
                items=[
                    "Предмет закупки: Раздел 1. Общие требования.",
                    "Оплата: 7 рабочих дней с подписания акта.",
                ],
            )
        ],
    )


def test_verified_original_overrides_false_subject_and_keeps_other_findings():
    step = requirements_step()
    original = [step]
    result = add_verified_notice_to_report_steps(metadata(), original)
    assert len(result) == 1
    amended = result[0]
    assert amended is not step
    assert step.findings[0] == "Предмет закупки: Раздел 1. Общие требования."
    assert SUBJECT in amended.findings[0]
    assert "eis-xml:FILE-01:purchaseObjectInfo" in amended.findings[0]
    assert "НМЦК: 1000000.00" in amended.findings[2]
    assert not any("Предмет закупки: Раздел 1." in x for x in amended.findings)
    assert "Оплата: 7 рабочих дней с подписания акта." in amended.findings
    assert amended.result_sections[0].title.startswith("Официальные факты")
    assert "из XML ЕИС" in amended.result_summary
    assert not any(
        "Предмет закупки: Раздел 1." in item
        for section in amended.result_sections
        for item in section.items
    )
    assert "Оплата: 7 рабочих дней с подписания акта." in amended.result_sections[1].items
    assert original[0].findings == step.findings
    assert original[0].result_sections[0].items[0] == "Предмет закупки: Раздел 1. Общие требования."


def test_wrong_registry_or_unmatched_file_never_promotes_eis_facts():
    current = metadata()
    current["_verified_notice_facts"]["registry_number"] = "1111111111111111111"
    old = [requirements_step()]
    assert add_verified_notice_to_report_steps(current, old) == old
    current = metadata()
    current["files"][0]["file_id"] = "FILE-02"
    assert add_verified_notice_to_report_steps(current, old) == old


def test_223_and_manual_upload_never_claim_44fz_original():
    old = [requirements_step()]
    for source in ["public_eis_html_223fz", "manual_upload", None]:
        assert add_verified_notice_to_report_steps(metadata(source), old) == old


def test_partial_xml_keeps_unknown_and_never_invents_price():
    current = metadata()
    current["_verified_notice_facts"]["values"].pop("nmck")
    amended = add_verified_notice_to_report_steps(current, [requirements_step()])
    assert SUBJECT in amended[0].findings[0]
    assert not any("НМЦК:" in item for item in amended[0].findings)
