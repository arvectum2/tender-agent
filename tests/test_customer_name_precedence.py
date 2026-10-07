"""Focused regression tests for customer_name source precedence.

EIS <placer> can identify the procurement organizer rather than the actual
customer.  An explicitly extracted document customer therefore has higher
semantic authority for customer_name.  All other metadata fields preserve
the existing eis_notice > card > documents precedence.
"""
from __future__ import annotations

from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    merge_structured_metadata,
)


def test_explicit_document_customer_wins_over_notice_placer() -> None:
    """TEST A — explicit document customer wins over EIS placer/organizer."""

    notice_meta = {
        "customer_name": 'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "ЦЕНТР МУНИЦИПАЛЬНЫХ ЗАКУПОК"',
    }
    card_meta: dict = {}
    doc_meta = {
        "customer_name": 'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ"',
    }

    merged = merge_structured_metadata(notice_meta, card_meta, doc_meta)

    assert merged["customer_name"]["value"] == 'МУНИЦИПАЛЬНОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "СЛУЖБА КЛАДБИЩ"'
    assert merged["customer_name"]["source"] == "documents"


def test_notice_fallback_when_no_document_customer() -> None:
    """TEST B — notice fallback preserved when document has no customer_name."""

    notice_meta = {
        "customer_name": "Заказчик из извещения",
    }
    card_meta: dict = {}
    doc_meta: dict = {}

    merged = merge_structured_metadata(notice_meta, card_meta, doc_meta)

    assert merged["customer_name"]["value"] == "Заказчик из извещения"
    assert merged["customer_name"]["source"] == "eis_notice"


def test_card_fallback_when_no_document_and_no_notice_customer() -> None:
    """TEST C — card fallback preserved when document and notice have no customer."""

    notice_meta: dict = {}
    card_meta = {
        "customer_name": "Заказчик из карточки",
    }
    doc_meta: dict = {}

    merged = merge_structured_metadata(notice_meta, card_meta, doc_meta)

    assert merged["customer_name"]["value"] == "Заказчик из карточки"
    assert merged["customer_name"]["source"] == "card"


def test_unrelated_field_precedence_unchanged() -> None:
    """TEST D — unrelated field precedence remains notice > card > documents."""

    notice_meta = {
        "nmck": 1000.0,
        "publication_date": "2026-01-01",
        "customer_name": "notice_customer",
    }
    card_meta = {
        "nmck": 2000.0,
        "publication_date": "2026-02-01",
        "customer_name": "card_customer",
    }
    doc_meta = {
        "nmck": 3000.0,
        "publication_date": "2026-03-01",
        "customer_name": "doc_customer",
    }

    merged = merge_structured_metadata(notice_meta, card_meta, doc_meta)

    # notice wins for all non-customer fields
    assert merged["initial_price"]["value"] == 1000.0
    assert merged["initial_price"]["source"] == "eis_notice"
    assert merged["publication_date"]["value"] == "2026-01-01"
    assert merged["publication_date"]["source"] == "eis_notice"

    # customer_name uses documents-first precedence
    assert merged["customer_name"]["value"] == "doc_customer"
    assert merged["customer_name"]["source"] == "documents"


def test_public_44fz_search_intake_keeps_explicit_card_customer_over_attachment_customer() -> None:
    from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
    from src.modules.tender_operator_agent_demo.upload_service import (
        _enrich_procurement_metadata_from_documents,
    )

    card_customer = 'ГОСУДАРСТВЕННОЕ КАЗЕННОЕ УЧРЕЖДЕНИЕ "КАРТОЧКА ЕИС"'
    metadata = {
        "mode": "procurement_search_intake",
        "procurement_source": "public_eis_html_44fz",
        "customer_name": card_customer,
        "tender_title": "Поставка кабельной продукции",
        "procurement": {
            "customer_name": card_customer,
            "title": "Поставка кабельной продукции",
            "source": "public_eis_html_44fz",
        },
    }
    contract = AnalyzedDocument(
        display_name="Проект контракта.docx",
        extension=".docx",
        role="contract_draft",
        text='Заказчик: ООО "НЕВЕРНЫЙ ЗАКАЗЧИК"',
        extracted_text_available=True,
        warnings=[],
        source="public_eis",
        file_id="contract-1",
    )

    enriched = _enrich_procurement_metadata_from_documents(
        metadata,
        documents=[contract],
        combined_text=contract.text,
        notice_text="",
        technical_spec_text="",
        contract_draft_text=contract.text,
    )

    assert enriched["customer_name"] == card_customer
    assert enriched["procurement"]["customer_name"] == card_customer
    assert enriched["_field_evidence"]["customer_name"] == "card:customer_name"
    assert enriched["procurement_title"] == "Поставка кабельной продукции"
    assert enriched["_field_evidence"]["procurement_title"] == "card:procurement_subject"
