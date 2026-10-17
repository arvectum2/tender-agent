"""First-party EIS docKindInfo must be bound to each real original, never outer ZIP container."""
from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.document_set_completeness import (
    build_document_set_summary,
)
from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    extract_notice_attachments,
)


def _item(name: str, uid: str, *, code: str | None, description: str | None) -> str:
    kind = (
        f"<docKindInfo><code>{code}</code><name>{description}</name></docKindInfo>"
        if code is not None and description is not None else ""
    )
    return (
        f"<attachmentInfo><fileName>{name}</fileName><fileSize>200</fileSize>"
        f"<url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={uid}</url>"
        f"{kind}</attachmentInfo>"
    )


def _notice(*items: str) -> str:
    return "<export><epNotificationEF2020><attachments>" + "".join(items) + "</attachments></epNotificationEF2020></export>"


def test_four_real_official_kinds_and_complete_document_gate() -> None:
    xml = _notice(
        _item("НМЦК.docx", "A"*32, code="MRJ",
              description="Обоснование начальной (максимальной) цены контракта"),
        _item("ПК.docx", "B"*32, code="CP", description="Проект контракта"),
        _item("ООЗ.docx", "C"*32, code="POD", description="Описание объекта закупки"),
        _item("Требования к заявке.docx", "D"*32, code="CAR",
              description="Требование к содержанию, составу заявки на участие в закупке"),
    )
    result = extract_notice_attachments(xml)
    assert len(result) == 4
    assert [x["name"] for x in result] == [
        "НМЦК.docx", "ПК.docx", "ООЗ.docx", "Требования к заявке.docx",
    ]
    assert [x["document_kind"] for x in result] == [
        "price_justification", "contract_draft",
        "procurement_object_description", "application_requirements",
    ]
    summary = build_document_set_summary([
        {"original_name": "epNotificationEF2020.xml", "role_hint": "notice", "extension": ".xml"},
        *[{"original_name": x["name"], "document_kind": x["document_kind"]} for x in result],
    ])
    assert summary["physical_file_count"] == 5
    assert summary["analysis_allowed"] is True
    assert summary["missing_required_document_kinds"] == []


@pytest.mark.parametrize("kind_code,kind_name", [
    ("CP", "Описание объекта закупки"),
    ("WRONG", "Проект контракта"),
    ("CP", "Проект   контракта несогласованный"),
    (None, None),
])
def test_unmatched_official_code_never_promotes_ambiguous_pk(kind_code, kind_name):
    rows = extract_notice_attachments(_notice(_item(
        "ПК.docx", "A"*32, code=kind_code, description=kind_name,
    )))
    assert len(rows) == 1
    assert rows[0]["document_kind"] == "attachment"
    assert not build_document_set_summary([
        {"original_name": "notice.xml", "role_hint": "notice"},
        {"original_name": "ООЗ.docx", "role_hint": "technical_spec"},
        {"original_name": "ПК.docx", "document_kind": rows[0]["document_kind"]},
    ])["analysis_allowed"]


def test_nested_same_url_collection_never_hides_first_attachment() -> None:
    rows = extract_notice_attachments(_notice(
        _item("ПК.docx", "A"*32, code="CP", description="Проект контракта"),
        _item("Описание объекта закупки.docx", "B"*32, code="POD",
              description="Описание объекта закупки"),
    ))
    assert len(rows) == 2
    assert rows[0]["document_kind"] == "contract_draft"
    assert rows[1]["document_kind"] == "procurement_object_description"


def test_duplicate_same_name_url_remains_one_attachment() -> None:
    single = _item("ПК.docx", "A"*32, code="CP", description="Проект контракта")
    rows = extract_notice_attachments(_notice(single, single))
    assert len(rows) == 1
    assert rows[0]["document_kind"] == "contract_draft"


def test_unrelated_outer_kind_does_not_fill_missing_inner_doc_kind() -> None:
    xml = (
        "<export><docKindInfo><code>CP</code><name>Проект контракта</name></docKindInfo>"
        "<attachments>" + _item("ПК.docx", "A"*32, code=None, description=None)
        + "</attachments></export>"
    )
    rows = extract_notice_attachments(xml)
    assert len(rows) == 1
    assert rows[0]["document_kind"] == "attachment"


def test_official_generic_additional_security_annex_is_not_contract_draft() -> None:
    rows = extract_notice_attachments(_notice(
        _item("Приложение 6 Обеспечение исполнения контракта.docx", "A" * 32,
              code="AD", description="Дополнительная информация и документы"),
        _item("Приложение 5 Проект контракта.docx", "B" * 32,
              code="CP", description="Проект контракта"),
    ))
    assert [r["document_kind"] for r in rows] == [
        "contract_performance_security", "contract_draft",
    ]
    assert not build_document_set_summary([
        {"original_name": "epNotificationEF2020.xml", "document_kind": "eis_notice"},
        {"original_name": rows[0]["name"], "document_kind": rows[0]["document_kind"]},
        {"original_name": "ООЗ.docx", "document_kind": "procurement_object_description"},
    ])["analysis_allowed"]


def test_unrelated_containing_contract_word_is_not_security_doc() -> None:
    rows = extract_notice_attachments(_notice(
        _item("Приложение к проекту контракта.docx", "B" * 32,
              code="AD", description="Дополнительная информация и документы"),
    ))
    assert len(rows) == 1
    assert rows[0]["document_kind"] != "contract_performance_security"
