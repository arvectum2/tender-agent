"""Official EIS pricereq is not a competitive bid intake.

The three IDs were confirmed by live first-party EIS cards on 2026-10-12.
These tests are offline and must not access EIS or modify production.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import procurement_intake_service as intake
from src.modules.tender_operator_agent_demo.eis_price_request_guard import (
    official_eis_price_request_source_error,
)
from src.modules.tender_operator_agent_demo.schemas import SearchResultHandoffRequest

REQUESTS = (
    "0148300050426000047",
    "0318200087026000163",
    "0348100024426000052",
)


@pytest.mark.parametrize("number", REQUESTS)
@pytest.mark.parametrize("page", ("common-info.html", "docs.html"))
def test_official_price_request_links_are_market_research_only(number: str, page: str):
    url = f"https://zakupki.gov.ru/epz/pricereq/card/{page}?reestrNumber={number}"
    assert (
        official_eis_price_request_source_error(
            url,
            number,
        )
        == "MARKET_RESEARCH_PRICE_REQUEST_ONLY"
    )


@pytest.mark.parametrize("number", REQUESTS)
def test_price_search_links_are_not_competitive_handoffs(number: str):
    url = (
        f"https://zakupki.gov.ru/epz/pricereq/search/results.html?searchString={number}"
    )
    assert (
        official_eis_price_request_source_error(
            url,
            number,
        )
        == "MARKET_RESEARCH_PRICE_REQUEST_ONLY"
    )


def test_wrong_registry_binding_rejected():
    assert (
        official_eis_price_request_source_error(
            f"https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber={REQUESTS[0]}",
            REQUESTS[1],
        )
        == "SOURCE_RECORD_ID_MISMATCH"
    )
    assert (
        official_eis_price_request_source_error(
            "https://zakupki.gov.ru/epz/pricereq/card/common-info.html",
            REQUESTS[0],
        )
        == "SOURCE_RECORD_ID_MISMATCH"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://zakupki.gov.ru.evil.example/epz/pricereq/card/common-info.html?reestrNumber=0318200087026000163",
        "http://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber=0318200087026000163",
        "https://zakupki.gov.ru@evil.example/epz/pricereq/card/common-info.html?reestrNumber=0318200087026000163",
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0318200087026000163",
        "https://zakupki.gov.ru/epz/pricereq.evil/card/common-info.html?reestrNumber=0318200087026000163",
    ],
)
def test_non_official_price_source_not_misidentified(url: str):
    assert official_eis_price_request_source_error(url, REQUESTS[1]) is None


@pytest.mark.parametrize("number", REQUESTS)
def test_competitive_handoff_fails_before_soap_or_filesystem(monkeypatch, number: str):
    def forbidden_settings():
        raise AssertionError("SOAP/settings must never be accessed")

    monkeypatch.setattr(intake, "get_zakupki_soap_settings", forbidden_settings)
    req = SearchResultHandoffRequest(
        reestr_number=number,
        law="44fz",
        source_url=f"https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber={number}",
        analyze_after_download=True,
        download_archive=True,
    )
    with pytest.raises(HTTPException) as err:
        intake.create_run_from_search_result(req)
    assert err.value.status_code == 422
    assert err.value.detail["code"] == "MARKET_RESEARCH_PRICE_REQUEST_ONLY"
    assert err.value.detail["record_type"] == "price_information_request"


def test_mismatched_card_cannot_be_submitted_to_soap(monkeypatch):
    monkeypatch.setattr(
        intake, "get_zakupki_soap_settings", lambda: pytest.fail("no SOAP")
    )
    with pytest.raises(HTTPException) as err:
        intake.create_run_from_search_result(
            SearchResultHandoffRequest(
                reestr_number=REQUESTS[2],
                source_url=f"https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber={REQUESTS[0]}",
            )
        )
    assert err.value.detail["code"] == "SOURCE_RECORD_ID_MISMATCH"


def test_non_price_sources_still_have_original_path():
    assert official_eis_price_request_source_error(None, REQUESTS[0]) is None
    assert (
        official_eis_price_request_source_error(
            f"https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber={REQUESTS[0]}",
            REQUESTS[0],
        )
        is None
    )
