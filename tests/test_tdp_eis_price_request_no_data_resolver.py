"""No-data is category-specific, not an absent registry record."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import procurement_intake_service as intake
from src.modules.tender_operator_agent_demo.eis_price_request_source_probe import (
    probe_exact_eis_price_request,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import DocsArchiveResult
from src.modules.tender_operator_agent_demo.schemas import EisDocsArchiveRunRequest

_NUMBERS=("0148300050426000047","0318200087026000163","0348100024426000052")
_TEXT=(
    "Карточка запроса цен товаров, работ, услуг "
    "№ {number} Общая информация запроса цен "
    "Проведение данной процедуры сбора информации не влечет за собой "
    "возникновение каких-либо обязательств заказчика."
)


def _html(number):
    return f"<html><body>{_TEXT.format(number=number)}</body></html>".encode()


@pytest.mark.parametrize("number",_NUMBERS)
def test_exact_official_registry_number_and_semantics_are_not_missing(number):
    source=probe_exact_eis_price_request(
        number,download=lambda url:(_html(number),url)
    )
    assert source is not None
    assert source["authority"]=="eis_official"
    assert source["procedure_type"]=="price_information_request"
    assert source["source_document_sha256"]==hashlib.sha256(_html(number)).hexdigest()
    assert source["bid_ready"]=="false"


@pytest.mark.parametrize("number",_NUMBERS)
def test_wrong_registry_identity_is_unverified_even_when_page_mentions_number(number):
    wrong=next(i for i in _NUMBERS if i!=number)
    assert probe_exact_eis_price_request(
        number,download=lambda url:(_html(wrong),url)
    ) is None


@pytest.mark.parametrize("page",[
    "Карточка запроса цен товаров, работ, услуг",
    "№ 0148300050426000047",
    "Общая информация запроса цен",
    "Проведение данной процедуры сбора информации не влечет",
])
def test_partial_official_page_or_search_navigation_is_not_verified(page):
    raw=f"<html><body>{page}</body></html>".encode()
    assert probe_exact_eis_price_request(
        _NUMBERS[0],download=lambda url:(raw,url)
    ) is None


def test_redirect_to_other_site_is_not_trusted():
    assert probe_exact_eis_price_request(
        _NUMBERS[0], download=lambda url:(_html(_NUMBERS[0]),"https://other.example/card")
    ) is None


def test_network_unavailability_and_invalid_registry_are_unknown_not_nonexistent():
    def timeout(_):
        raise TimeoutError("offline")
    assert probe_exact_eis_price_request(_NUMBERS[0],download=timeout) is None
    assert probe_exact_eis_price_request("not_a_registry_number",download=timeout) is None


def test_pipeline_catches_official_price_registry_before_artifact_generation(monkeypatch):
    number=_NUMBERS[0]

    class FakeClient:
        def __init__(self,_settings):
            pass
        def get_docs_by_reestr_number(self,_n,subsystem_type="PRIZ"):
            assert _n==number
            return DocsArchiveResult(
                request_id="rq",ref_id="ref",archive_url=None,
                archive_urls=[],status="no_data",warnings=[],
            )

    monkeypatch.setattr(intake,"get_zakupki_soap_settings",lambda:type("Settings",(),{"configured":True})())
    monkeypatch.setattr(intake,"ZakupkiSoapClient",FakeClient)
    monkeypatch.setattr(intake,"ensure_demo_run_structure",lambda *a,**kw:pytest.fail("do not create false bid run"))
    import src.modules.tender_operator_agent_demo.eis_price_request_source_probe as probe_module
    monkeypatch.setattr(probe_module,"probe_exact_eis_price_request",lambda n: {
        "procedure_type":"price_information_request",
        "authority":"eis_official",
        "procurement_id":n,
        "official_source_url":"https://zakupki.gov.ru/epz/pricereq/card/common-info.html?reestrNumber="+n,
        "source_document_sha256":"a"*64,
    })
    with pytest.raises(HTTPException) as err:
        intake.create_run_from_eis_docs_archive(EisDocsArchiveRunRequest(reestr_number=number))
    assert err.value.status_code==422
    assert err.value.detail["code"]=="MARKET_RESEARCH_PRICE_REQUEST_ONLY"
    assert "запросов ценовой" in err.value.detail["message"]
    assert "https://zakupki.gov.ru" in err.value.detail["official_source_url"]


def test_no_archive_summary_is_plain_language_not_transport_code():
    source=DocsArchiveResult(
        request_id="rq",ref_id="ref",archive_url=None,
        archive_urls=[],status="no_data",warnings=[],
        raw_summary="getDocsIP no_data",
    )
    selected=intake._build_getdocs_result(_NUMBERS[0],source)
    assert "не подтверждает отсутствие" in selected.summary
    assert "no_data" not in selected.summary
    assert "getDocsIP" not in selected.summary
    assert "Read-only" not in selected.source_note


@pytest.mark.parametrize("number",_NUMBERS)
def test_mac_mini_original_primary_cards_replay_offline_if_available(number):
    root=os.environ.get("TA_PRIVATE_EIS_PRICE_REQUEST_ORIGINALS")
    if not root:
        pytest.skip("private original evidence absent in GitHub runner")
    raw=(Path(root)/f"{number}-card.html").read_bytes()
    result=probe_exact_eis_price_request(number,download=lambda url:(raw,url))
    assert result is not None
    assert result["source_document_sha256"]==hashlib.sha256(raw).hexdigest()
