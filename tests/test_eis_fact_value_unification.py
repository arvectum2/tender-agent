"""Same source fact rules for original-file extraction and report projection."""

from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.eis_fact_values import (
    EIS_NOTICE_FACT_TAGS,
    verified_eis_fact_value,
)


def test_single_canonical_eis_source_schema():
    assert EIS_NOTICE_FACT_TAGS == (
        ("procurement_title", "purchaseObjectInfo"),
        ("application_deadline", "endDT"),
        ("nmck", "maxPrice"),
    )
    assert verified_eis_fact_value("procurement_title", "Создание сайта") == "Создание сайта"
    assert verified_eis_fact_value("nmck", "1000000.00") == 1000000.0
    assert verified_eis_fact_value("application_deadline", "2026-10-16T10:00:00+03:00") == "2026-10-16T10:00:00+03:00"


@pytest.mark.parametrize("field,raw", [
    ("nmck", "-10"),
    ("nmck", "NaN"),
    ("nmck", "Infinity"),
    ("nmck", "1E+10000"),
    ("nmck", "text"),
    ("application_deadline", "2026-10-16"),
    ("application_deadline", "not a date"),
    ("procurement_title", ""),
    ("procurement_title", "x" * 4097),
    ("untrusted_other", "unexpected"),
])
def test_invalid_eis_fact_never_promoted(field, raw):
    assert verified_eis_fact_value(field, raw) is None
