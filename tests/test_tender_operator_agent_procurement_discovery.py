import pytest
from datetime import date
from urllib.parse import unquote

from src.modules.tender_operator_agent_demo.procurement_discovery import (
    _filter_public_44fz_cards,
    build_public_search_url,
    list_procurement_sources,
    search_public_44fz,
    search_procurements,
)
from src.modules.tender_operator_agent_demo.procurement_schemas import ProcurementSearchRequest
from src.modules.tender_operator_agent_demo.settings import clear_zakupki_soap_settings_cache


def test_demo_local_procurement_search_returns_results(client):
    response = client.get(
        "/api/demo/tender-agent/procurements/search",
        params={"query": "электротехническое оборудование", "source": "demo_local", "max_results": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "demo_local"
    assert payload["results"]
    first = payload["results"][0]
    assert first["procurement_id"]
    assert first["title"]
    assert first["customer_name"] == "Промышленный заказчик"
    assert first["attachments_status"] in {
        "downloadable",
        "manual_upload_required",
        "unavailable_in_demo",
        "source_requires_authorization",
    }
    assert payload["sources"]


def test_unknown_procurement_source_is_rejected(client):
    response = client.get(
        "/api/demo/tender-agent/procurements/search",
        params={"query": "кабель", "source": "unknown_source"},
    )

    assert response.status_code == 400
    assert "Unknown procurement source" in response.json()["detail"]


def test_disabled_procurement_source_returns_warning(client):
    response = client.get(
        "/api/demo/tender-agent/procurements/search",
        params={"query": "кабель", "source": "public_eis_html_44fz"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == []
    assert payload["warnings"]


def test_procurement_sources_include_zakupki_disabled_without_token(monkeypatch):
    monkeypatch.setattr("src.modules.tender_operator_agent_demo.settings._seed_env_from_local_files", lambda: None)
    monkeypatch.delenv("ZAKUPKI_GOV_RU_SOAP_ENABLED", raising=False)
    monkeypatch.delenv("ZAKUPKI_GOV_RU_SOAP_TOKEN", raising=False)
    clear_zakupki_soap_settings_cache()

    sources = {item.source: item for item in list_procurement_sources()}

    assert sources["demo_local"].configured is True
    assert sources["public_eis_html_44fz"].configured is True
    assert sources["public_eis_html_capital_repair"].configured is True
    assert sources["zakupki_gov_ru_getdocs_ip"].configured is False
    assert "не настроен" in (sources["zakupki_gov_ru_getdocs_ip"].reason or "")


def test_procurement_discovery_request_schema_searches_demo_local():
    results = search_procurements(
        ProcurementSearchRequest(source="demo_local", query="кабель", max_results=3)
    )

    assert results
    assert results[0].notice_number
    assert results[0].source == "demo_local"
    assert results[0].attachments_count >= 0


def test_procurement_discovery_unknown_source_rejected_directly():
    with pytest.raises(ValueError, match="Unknown procurement source"):
        search_procurements(ProcurementSearchRequest(source="unknown_source", query="кабель"))


def test_public_search_url_is_built_for_44fz():
    payload = build_public_search_url(query="кабель", law="44fz", region="77")

    assert payload.source == "public_eis_html_44fz"
    assert "extendedsearch" in payload.eis_search_url
    assert "кабель" in unquote(payload.eis_search_url)
    assert payload.note


def test_public_search_url_is_built_for_capital_repair():
    payload = build_public_search_url(query="ремонт", law="capital_repair")

    assert payload.source == "public_eis_html_capital_repair"
    assert "ppRf615=on" in payload.eis_search_url


def test_getdocs_source_returns_empty_results_in_search_mode():
    with pytest.raises(RuntimeError, match="не настроен|не поддерживает keyword search"):
        search_procurements(ProcurementSearchRequest(source="zakupki_gov_ru_getdocs_ip", query="кабель"))


def test_public_44fz_filter_helper_applies_status_procedure_and_deadline():
    cards = [
        {
            "title": "Закупка 1",
            "status": "Подача заявок",
            "procedure_type": "Электронный аукцион",
            "publication_date": "01.07.2026",
            "deadline": "10.07.2026",
            "initial_price": 1000000.0,
        },
        {
            "title": "Закупка 2",
            "status": "Закупка завершена",
            "procedure_type": "Запрос котировок",
            "publication_date": "20.06.2026",
            "deadline": "25.06.2026",
            "initial_price": 500000.0,
        },
    ]

    filtered = _filter_public_44fz_cards(
        cards,
        status_filter="Подача заявок",
        procedure_type="Электронный аукцион",
        deadline_from="2026-07-01",
        deadline_to="2026-07-15",
    )

    assert len(filtered) == 1
    assert filtered[0]["title"] == "Закупка 1"


def test_public_44fz_filter_helper_drops_expired_submission_status(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 6)

    monkeypatch.setattr(discovery, "date", FixedDate)

    cards = [
        {
            "title": "Просроченная закупка",
            "status": "Подача заявок",
            "procedure_type": "Электронный аукцион",
            "publication_date": "01.07.2026",
            "deadline": "05.07.2026",
            "initial_price": 1000000.0,
        },
        {
            "title": "Актуальная закупка",
            "status": "Подача заявок",
            "procedure_type": "Электронный аукцион",
            "publication_date": "01.07.2026",
            "deadline": "07.07.2026",
            "initial_price": 1000000.0,
        },
    ]

    filtered = _filter_public_44fz_cards(cards)

    assert [card["title"] for card in filtered] == ["Актуальная закупка"]


def test_public_44fz_search_uses_post_filters(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "parsed", "html": "<html></html>", "error": None},
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка 1",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "01.07.2026",
                "deadline": "10.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=1",
                "law": "44fz",
                "warnings": [],
            },
            {
                "title": "Закупка 2",
                "notice_number": "2",
                "reestr_number": "2",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "01.07.2026",
                "deadline": "10.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Запрос котировок",
                "source_url": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=2",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="223fz",
        status_filter="Подача заявок",
        procedure_type="Электронный аукцион",
        deadline_from="2026-07-01",
        deadline_to="2026-07-15",
        max_results=5,
    )

    assert result["status"] == "parsed"
    assert len(result["cards"]) == 1
    assert result["cards"][0]["notice_number"] == "1"
    assert result["cards"][0]["law"] == "223fz"
    assert result["cards"][0]["source"] == "public_eis_html_223fz"


def test_public_44fz_search_returns_success_empty_after_post_filters(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "parsed", "html": "<html></html>", "error": None},
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка 1",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "01.07.2026",
                "deadline": "10.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Запрос котировок",
                "source_url": "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        procedure_type="Электронный аукцион",
        max_results=5,
    )

    assert result["status"] == "empty_results"
    assert result["outcome"] == "success_empty"
    assert result["cards"] == []
    assert "не найдены" in result["message"]


def test_public_44fz_search_returns_source_unavailable_for_js_heavy(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "js_heavy", "html": None, "error": None},
    )

    result = search_public_44fz(query="тест", law="44fz")

    assert result["status"] == "js_heavy"
    assert result["outcome"] == "source_unavailable"
    assert result["cards"] == []
    assert "недоступен" in result["message"]


def test_public_44fz_search_by_exact_notice_number_skips_supplier_relevance(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "parsed", "html": "<html></html>", "error": None},
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Тестовая закупка по номеру",
                "notice_number": "0888500000226000399",
                "reestr_number": "0888500000226000399",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "07.07.2026",
                "deadline": "15.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0888500000226000399",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(query="0888500000226000399", law="44fz", max_results=5)

    assert result["status"] == "parsed"
    assert len(result["cards"]) == 1
    assert "relevance" not in result["cards"][0]


def test_public_44fz_exact_number_search_isolated_from_supplier_relevance_state(monkeypatch):
    """Exact-number calls must neither consume nor mutate relevance state."""
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    card = {
        "title": "Тестовая закупка",
        "notice_number": "0888500000226000399",
        "reestr_number": "0888500000226000399",
        "customer_name": "Заказчик",
        "initial_price": 1000000.0,
        "publication_date": "07.07.2026",
        "deadline": "15.07.2026",
        "status": "Закупка завершена",
        "procedure_type": "Электронный аукцион",
        "source_url": "https://zakupki.gov.ru/notice?regNumber=0888500000226000399",
        "law": "44fz",
        "warnings": [],
    }
    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "parsed", "html": "<html></html>", "error": None},
    )
    monkeypatch.setattr(discovery, "parse_44fz_search_results", lambda html: [card])

    relevance_calls: list[str] = []

    class Score:
        def to_dict(self):
            return {"status": "relevant"}

    def score(**kwargs):
        relevance_calls.append(kwargs["title"])
        return Score()

    monkeypatch.setattr(discovery, "score_procurement_card", score)

    ordinary_first = discovery.search_public_44fz(query="тест", law="44fz", max_results=1)
    exact_first = discovery.search_public_44fz(query=card["notice_number"], law="44fz", max_results=1)
    ordinary_second = discovery.search_public_44fz(query="тест", law="44fz", max_results=1)
    exact_second = discovery.search_public_44fz(query=card["notice_number"], law="44fz", max_results=1)

    assert [result["status"] for result in (ordinary_first, exact_first, ordinary_second, exact_second)] == ["parsed"] * 4
    assert all("relevance" in result["cards"][0] for result in (ordinary_first, ordinary_second))
    assert all("relevance" not in result["cards"][0] for result in (exact_first, exact_second))
    assert relevance_calls == [card["title"], card["title"]]


def test_public_44fz_search_backfill_fills_to_page_size(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    call_count: list[int] = []

    def fake_fetch(url: str):
        call_count.append(len(call_count) + 1)
        page_num = call_count[-1]
        if page_num == 1:
            return {
                "status": "parsed",
                "html": '<a onclick="downloadCsv(\'?searchString=test\', \'100\')"></a>',
                "error": None,
            }
        return {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'100\')"></a>',
            "error": None,
        }

    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", fake_fetch)
    cards_page1 = [
        {
            "title": f"Закупка {i}",
            "notice_number": str(i),
            "reestr_number": str(i),
            "customer_name": "Заказчик",
            "initial_price": 1000000.0,
            "publication_date": "01.06.2026",
            "deadline": "01.01.2020",
            "status": "Подача заявок",
            "procedure_type": "Электронный аукцион",
            "source_url": f"https://zakupki.gov.ru/{i}",
            "law": "44fz",
            "warnings": [],
        }
        for i in range(1, 11)
    ]

    def fake_parse(html):
        page_num = call_count[-1] if call_count else 1
        cards = list(cards_page1)
        if page_num == 2:
            cards = [
                {
                    "title": f"Backfill {i}",
                    "notice_number": f"b{i}",
                    "reestr_number": f"b{i}",
                    "customer_name": "Заказчик",
                    "initial_price": 2000000.0,
                    "publication_date": "06.07.2026",
                    "deadline": "20.07.2026",
                    "status": "Подача заявок",
                    "procedure_type": "Электронный аукцион",
                    "source_url": f"https://zakupki.gov.ru/b{i}",
                    "law": "44fz",
                    "warnings": [],
                }
                for i in range(1, 11)
            ]
        return cards

    monkeypatch.setattr(discovery, "parse_44fz_search_results", fake_parse)

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        reference_date=date(2026, 7, 10),
    )

    assert result["status"] == "parsed"
    assert result["returned_count"] == 10
    assert result["local_filtered_count"] >= 1
    assert result["local_post_filter_applied"] is True
    assert result["eis_pages_fetched"] >= 2
    assert result["total_count"] == 100
    assert result["total_count_exact_for_displayed_filters"] is False
    assert result["total_count_source"] == "eis_download_csv"
    assert result["raw_returned_count"] is not None
    assert result["has_more"] is True
    assert result["next_cursor"] is not None


def test_public_44fz_search_backfill_limit_not_exceeded(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    call_count: list[int] = []

    def fake_fetch(url: str):
        call_count.append(len(call_count) + 1)
        return {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'500\')"></a>',
            "error": None,
        }

    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", fake_fetch)

    original_filter = discovery._filter_public_44fz_cards

    def restrictive_filter(cards, **kwargs):
        filtered = original_filter(cards, **kwargs)
        if filtered:
            return filtered[:1]
        return filtered

    monkeypatch.setattr(discovery, "_filter_public_44fz_cards", restrictive_filter)

    def fake_parse(html):
        return [
            {
                "title": f"Закупка {i}",
                "notice_number": str(i),
                "reestr_number": str(i),
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": f"https://zakupki.gov.ru/{i}",
                "law": "44fz",
                "warnings": [],
            }
            for i in range(1, 11)
        ]

    monkeypatch.setattr(discovery, "parse_44fz_search_results", fake_parse)

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        reference_date=date(2026, 7, 10),
    )

    assert result["status"] == "parsed"
    assert result["returned_count"] <= 10
    assert result["eis_pages_fetched"] <= discovery.MAX_BACKFILL_PAGES


def test_public_44fz_search_no_duplicates_with_cursor(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    fetch_call_index: list[int] = [0]

    def fake_fetch(url: str):
        fetch_call_index[0] += 1
        return {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'50\')"></a>',
            "error": None,
        }

    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", fake_fetch)

    cards_page1 = [
        {
            "title": f"Page1 {i}",
            "notice_number": str(i),
            "reestr_number": str(i),
            "customer_name": "Заказчик",
            "initial_price": 1000000.0,
            "publication_date": "06.07.2026",
            "deadline": "12.07.2026",
            "status": "Подача заявок",
            "procedure_type": "Электронный аукцион",
            "source_url": f"https://zakupki.gov.ru/{i}",
            "law": "44fz",
            "warnings": [],
        }
        for i in range(1, 11)
    ]
    cards_page2 = [
        {
            "title": f"Page2 {i}",
            "notice_number": str(i + 10),
            "reestr_number": str(i + 10),
            "customer_name": "Заказчик",
            "initial_price": 2000000.0,
            "publication_date": "06.07.2026",
            "deadline": "12.07.2026",
            "status": "Закупка завершена",
            "procedure_type": "Электронный аукцион",
            "source_url": f"https://zakupki.gov.ru/{i + 10}",
            "law": "44fz",
            "warnings": [],
        }
        for i in range(1, 11)
    ]

    def fake_parse_page1(html):
        return list(cards_page1)

    def fake_parse_page2(html):
        return list(cards_page2)

    monkeypatch.setattr(discovery, "parse_44fz_search_results", fake_parse_page1)

    page1_result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        reference_date=date(2026, 7, 10),
    )

    assert page1_result["returned_count"] == 10
    assert page1_result["next_cursor"] is not None

    page1_numbers = {c["notice_number"] for c in page1_result["cards"]}

    monkeypatch.setattr(discovery, "parse_44fz_search_results", fake_parse_page2)

    cursor = page1_result["next_cursor"]
    page2_result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        cursor=cursor,
    )

    assert page2_result["returned_count"] >= 1
    page2_numbers = {c["notice_number"] for c in page2_result["cards"]}
    assert page1_numbers.isdisjoint(page2_numbers)


def test_public_44fz_search_rejects_cursor_for_other_filters(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {"status": "parsed", "html": "<html></html>", "error": None},
    )
    monkeypatch.setattr(discovery, "parse_44fz_search_results", lambda html: [])

    cursor = discovery._encode_search_cursor(
        query="кабель",
        filters=discovery._build_cursor_filters(law="44fz"),
        next_eis_page=2,
        seen_registry_numbers=["1"],
        page_size=10,
    )

    with pytest.raises(ValueError, match="не соответствует"):
        search_public_44fz(query="поставка", law="44fz", cursor=cursor)


def test_public_44fz_search_exact_total_true_when_native_only(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'24\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
            {
                "title": "Закупка 2",
                "notice_number": "2",
                "reestr_number": "2",
                "customer_name": "Заказчик",
                "initial_price": 2000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/2",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
    )

    assert result["total_count"] == 24
    assert result["total_count_exact_for_displayed_filters"] is True
    assert result["local_filtered_count"] == 0
    assert result["local_post_filter_applied"] is False


def test_public_44fz_search_exact_total_false_when_local_filter_applied(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'99\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
            {
                "title": "Закупка с истёкшим сроком",
                "notice_number": "2",
                "reestr_number": "2",
                "customer_name": "Заказчик",
                "initial_price": 2000000.0,
                "publication_date": "06.07.2026",
                "deadline": "01.01.2020",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/2",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
    )

    assert result["total_count"] == 99
    assert result["total_count_exact_for_displayed_filters"] is False
    assert result["local_post_filter_applied"] is True
    assert result["local_filtered_count"] >= 1


def test_public_44fz_search_exact_total_false_when_non_native_filter(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'150\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        region="77",
    )

    assert result["total_count"] == 150
    assert result["total_count_exact_for_displayed_filters"] is False


def test_public_44fz_search_returned_count_reflects_backfill(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'50\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": f"Закупка {i}",
                "notice_number": str(i),
                "reestr_number": str(i),
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": f"https://zakupki.gov.ru/{i}",
                "law": "44fz",
                "warnings": [],
            }
            for i in range(1, 10)
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
        reference_date=date(2026, 7, 10),
    )

    assert result["status"] == "parsed"
    assert result["returned_count"] <= 10


def test_public_44fz_search_parser_status_includes_diagnostics(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'24\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=1,
        page_size=10,
        max_results=10,
    )

    assert "raw_returned_count" in result
    assert "local_filtered_count" in result
    assert "local_post_filter_applied" in result
    assert "eis_pages_fetched" in result
    assert "total_count_source" in result
    assert "total_count_exact_for_displayed_filters" in result
    assert "next_cursor" in result


def test_public_44fz_search_validation_error_cursor_not_affected(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'24\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Закупка завершена",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(query="", law="44fz")

    assert result["status"] == "validation_error"
    assert result["cards"] == []


def test_public_44fz_search_validation_error_for_empty_query():
    result = search_public_44fz(query="", law="44fz")

    assert result["status"] == "validation_error"
    assert result["outcome"] == "validation_error"
    assert result["cards"] == []
    assert result["error"]


def test_public_44fz_search_returns_pagination_fields_and_date_desc(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<div class="search-results__total">24 записи</div>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Старая закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000.0,
                "publication_date": "01.07.2026",
                "deadline": "10.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
            {
                "title": "Новая закупка",
                "notice_number": "2",
                "reestr_number": "2",
                "customer_name": "Заказчик",
                "initial_price": 2000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/2",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        page=2,
        page_size=10,
        max_results=10,
        reference_date=date(2026, 7, 6),
    )

    assert result["page"] == 2
    assert result["page_size"] == 10
    assert result["returned_count"] == 2
    assert result["total_count"] == 24
    assert result["has_more"] is True
    assert result["next_page"] is None
    assert result["next_cursor"] is not None
    assert result["sort"] == "publication_date_desc"
    assert "следующие" in result["message"].lower() or "карточки" in result["message"].lower()
    assert "24" in result["message"]
    assert [card["notice_number"] for card in result["cards"]] == ["2", "1"]


def test_public_44fz_search_pushes_status_filter_to_eis_and_keeps_exact_total(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    captured: dict[str, str] = {}

    def fake_fetch(url: str):
        captured["url"] = url
        return {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'12\')"></a>',
            "error": None,
        }

    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", fake_fetch)
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Определение поставщика завершено",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(
        query="тест",
        law="44fz",
        status_filter="Закупка завершена",
        page=1,
        page_size=10,
        max_results=10,
    )

    assert "pc=on" in captured["url"]
    assert result["total_count"] == 12
    assert result["returned_count"] == 1
    assert result["message"] == "Показаны первые 1 карточек из 12."
    assert result["cards"][0]["notice_number"] == "1"


def test_public_44fz_search_drops_exact_total_for_non_native_filters(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(
        discovery,
        "fetch_public_44fz_search_page",
        lambda url: {
            "status": "parsed",
            "html": '<a onclick="downloadCsv(\'?searchString=test\', \'99\')"></a>',
            "error": None,
        },
    )
    monkeypatch.setattr(
        discovery,
        "parse_44fz_search_results",
        lambda html: [
            {
                "title": "Закупка",
                "notice_number": "1",
                "reestr_number": "1",
                "customer_name": "Заказчик",
                "initial_price": 1000.0,
                "publication_date": "06.07.2026",
                "deadline": "12.07.2026",
                "status": "Подача заявок",
                "procedure_type": "Электронный аукцион",
                "source_url": "https://zakupki.gov.ru/1",
                "law": "44fz",
                "warnings": [],
            },
        ],
    )

    result = search_public_44fz(query="тест", law="44fz", procedure_type="Электронный аукцион", page=1, page_size=10, max_results=10, reference_date=date(2026, 7, 10))

    assert result["total_count"] == 99
    assert result["total_count_exact_for_displayed_filters"] is False
    assert "ЕИС найдено" in result["message"]


def test_company_search_skips_global_score_and_limits_backfill(monkeypatch):
    from datetime import date

    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    calls = []

    def fetch(url):
        calls.append(url)
        return {"status": "parsed", "html": "<html></html>"} if len(calls) == 1 else {"status": "timeout", "html": None}

    def global_profile():
        raise AssertionError("Company discovery must never read the global supplier profile")

    monkeypatch.setattr(discovery, "get_supplier_profile", global_profile)
    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", fetch)
    monkeypatch.setattr(discovery, "parse_44fz_search_results", lambda _: [{
        "title": "Разработка сайта", "notice_number": "0123456789012345678", "reestr_number": "0123456789012345678",
        "customer_name": "Заказчик", "initial_price": 500000, "publication_date": "15.11.2026",
        "deadline": "30.11.2026", "status": "Подача заявок", "procedure_type": "Электронный аукцион", "warnings": [],
    } for _ in range(10)])
    result = discovery.search_public_44fz(query="разработка", reference_date=date(2026, 11, 15),
                                           max_results=10, apply_supplier_relevance=False, backfill_page_limit=2)
    assert len(calls) == 2 and len(result["cards"]) == 1
    assert "relevance" not in result["cards"][0]
    assert result["source_coverage_complete"] is False


def test_company_search_blank_response_is_not_proof_of_empty(monkeypatch):
    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", lambda _: {"status": "empty_results", "html": None})
    result = discovery.search_public_44fz(query="разработка", apply_supplier_relevance=False)
    assert result["outcome"] == "success_empty"
    assert result["source_coverage_complete"] is False
    monkeypatch.setattr(discovery, "fetch_public_44fz_search_page", lambda _: {"status": "empty_results", "html": None, "explicit_zero_count": True})
    assert discovery.search_public_44fz(query="разработка", apply_supplier_relevance=False)["source_coverage_complete"] is True
    assert discovery.search_public_44fz(query="разработка", region="Москва", apply_supplier_relevance=False)["source_coverage_complete"] is False
