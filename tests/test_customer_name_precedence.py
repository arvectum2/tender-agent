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
