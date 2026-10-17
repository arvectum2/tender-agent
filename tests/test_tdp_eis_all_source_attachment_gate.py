"""Competitive analysis must account for EVERY file in the selected EIS notice."""
from __future__ import annotations

from types import SimpleNamespace

from src.modules.tender_operator_agent_demo.document_set_completeness import (
    apply_document_set_summary,
)
from src.modules.tender_operator_agent_demo.eis_original_attachment_completeness import (
    check_eis_attachment_completeness,
    expected_eis_notice_attachments,
)
from src.modules.tender_operator_agent_demo.procurement_intake_service import (
    _dedupe_procurement_attachments,
)


def _source(index: int) -> str:
    return (
        "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html"
        f"?uid={index:032X}"
    )


def _attachments():
    return [
        SimpleNamespace(name="Проект контракта.docx", url=_source(1)),
        SimpleNamespace(name="Техническое задание.docx", url=_source(2)),
        SimpleNamespace(name="Дополнительные требования.docx", url=_source(3)),
    ]


def _metadata(attachment_count: int) -> dict:
    items = [
        {"original_name": "Проект контракта.docx", "role_hint": "contract_draft"},
        {"original_name": "Техническое задание.docx", "role_hint": "technical_spec"},
    ]
    for a in _attachments()[:attachment_count]:
        items.append({
            "original_name": a.name,
            "source_type": "notice_xml_attachments",
            "source_url": a.url,
        })
    return {
        "source": "zakupki_gov_ru_getdocs_ip",
        "files": items,
        "official_xml_attachment_inventory": expected_eis_notice_attachments(_attachments()),
    }


def test_contract_and_technical_spec_do_not_overrule_missing_source_appendix():
    incomplete = apply_document_set_summary(_metadata(2))
    assert incomplete["missing_required_document_kinds"] == []
    assert incomplete["status"] == "incomplete_original_attachments"
    assert incomplete["analysis_allowed"] is False
    official = incomplete["official_original_attachments"]
    assert official["official_original_attachments_announced"] == 3
    assert official["official_original_attachments_downloaded"] == 2
    assert official["official_original_attachments_missing"] == 1

    complete = apply_document_set_summary(_metadata(3))
    assert complete["status"] == "complete"
    assert complete["analysis_allowed"] is True
    assert complete["official_original_attachments"]["official_original_attachments_missing"] == 0


def test_same_filename_with_two_different_official_links_is_not_deduplicated():
    a = SimpleNamespace(name="Проект контракта.docx", url=_source(1))
    b = SimpleNamespace(name="Проект контракта.docx", url=_source(2))
    c = SimpleNamespace(name="Иной файл.docx", url=_source(2))
    result = _dedupe_procurement_attachments([a, b, c], existing_files=[])
    assert [x.url for x in result] == [_source(1), _source(2)]
    saved = [
        {"original_name": "Проект контракта.docx", "source_url": _source(1)},
    ]
    filtered = _dedupe_procurement_attachments([a, b], existing_files=saved)
    assert [x.url for x in filtered] == [_source(2)]


def test_unresolved_official_source_link_blocks_analysis():
    planned = [
        SimpleNamespace(url=_source(1)),
        SimpleNamespace(url=None),
    ]
    expected = expected_eis_notice_attachments(planned)
    actual = [{"source_type": "notice_xml_attachments", "source_url": _source(1)}]
    status = check_eis_attachment_completeness(expected, actual)
    assert status["official_original_attachments_announced"] == 2
    assert status["official_original_attachments_missing"] == 1
    assert status["all_original_attachments_ready_for_analysis"] is False
    # Technical metadata stores hashed URLs, not original UID links.
    assert _source(1) not in str(expected)


def test_no_originals_never_automatically_authorize_legal_analysis():
    status = check_eis_attachment_completeness(
        expected_eis_notice_attachments([]), []
    )
    assert status["official_original_attachments_announced"] == 0
    assert status["all_original_attachments_ready_for_analysis"] is False
