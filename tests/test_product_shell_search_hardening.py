from src.modules.tender_operator_agent_demo.procurement_discovery import (
    _enrich_public_search_cards,
    _matches_public_card_query,
    _normalize_public_search_query,
    _should_apply_strict_query_filter,
    list_procurement_sources,
    score_public_query_match,
)
from src.modules.tender_operator_agent_demo.public_44fz_parser import (
    parse_44fz_search_results,
)
from src.modules.tender_operator_agent_demo.ui import (
    render_tender_operator_console_html,
)

AXIOMA_TITLE = (
    'Оказание услуг по разработке модуля для определения пересечений границ земельных '
    'участков с землями лесного фонда для программного обеспечения '
    '«Автоматизированная географическая информационная система «Аксиома»'
)


def test_software_abbreviation_is_expanded_for_public_search():
    normalized = _normalize_public_search_query('разработка ПО')
    assert normalized == 'разработка программного обеспечения'
    assert _should_apply_strict_query_filter('разработка ПО', normalized) is True
    assert _should_apply_strict_query_filter('разработка программн обеспеч', 'разработка программн обеспеч') is True
    assert _should_apply_strict_query_filter('тест', 'тест') is False


def test_truncated_software_query_matches_axioma_title():
    assert _matches_public_card_query(AXIOMA_TITLE, 'разработка программн обеспеч') is True
    score = score_public_query_match('разработка программн обеспеч', AXIOMA_TITLE)
    assert score['score'] == 100.0
    assert score['matched_terms'] == 3
    assert score['total_terms'] == 3


def test_software_query_rejects_generic_development_noise():
    title = 'Разработка проектно-сметной документации на капитальный ремонт здания'
    assert _matches_public_card_query(title, 'разработка ПО') is False


def test_missing_search_customer_is_enriched_from_common_info(monkeypatch):
    from datetime import datetime, timezone

    import src.modules.tender_operator_agent_demo.procurement_discovery as discovery

    class Detail:
        network_status = 'success'
        customer_name = 'ДЕПАРТАМЕНТ НЕДРОПОЛЬЗОВАНИЯ И ПРИРОДНЫХ РЕСУРСОВ ХМАО - ЮГРЫ'
        application_deadline = datetime(2026, 10, 5, 5, 0, tzinfo=timezone.utc)

    class Provider:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_detail(self, **kwargs):
            assert kwargs['registry_number'] == '0187200001726001304'
            return Detail()

    monkeypatch.setattr(discovery, 'Public44FzSearchProvider', Provider)
    [card] = _enrich_public_search_cards([
        {
            'reestr_number': '0187200001726001304',
            'source_url': 'https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0187200001726001304',
            'title': AXIOMA_TITLE,
            'customer_name': None,
            'deadline': None,
        }
    ])
    assert card['customer_name'].startswith('ДЕПАРТАМЕНТ НЕДРОПОЛЬЗОВАНИЯ')
    assert card['customer_identity_source'] == 'eis_common_info'
    assert card['deadline'] == '05.10.2026 05:00'


def test_search_parser_rejects_javascript_contaminated_customer():
    html = '''<html><body><div class="registry-entry">
      <div class="registry-entry__header-mid__title">Электронный аукцион</div>
      <div class="registry-entry__header-mid__number">
        <a href="/epz/order/notice/ea20/view/common-info.html?regNumber=0187200001726001304">0187200001726001304</a>
      </div>
      <div class="registry-entry__body-title">Заказчик</div>
      <div class="registry-entry__body-value">checkbox").prop("checked", false); function get_controller_table_customer() { return "bad"; }</div>
      <div class="registry-entry__body-title">Объект закупки</div>
      <div class="registry-entry__body-value">Оказание услуг по разработке программного обеспечения</div>
      <div class="data-block__title">Размещено</div>
      <div class="data-block__value">23.09.2026</div>
    </div></body></html>'''
    cards = parse_44fz_search_results(html)
    assert len(cards) == 1
    assert cards[0]['customer_name'] is None


def test_public_search_source_diagnostics_do_not_require_soap_token():
    source = next(item for item in list_procurement_sources() if item.source == 'public_eis_html_44fz')
    assert source.configured is True
    assert source.safe_diagnostics['mode'] == 'public_html_read_only'
    assert source.safe_diagnostics['auth_required'] is False
    assert source.safe_diagnostics['endpoint_host'] == 'zakupki.gov.ru'


def test_ui_exposes_active_status_filter_and_query_match_semantics(client):
    html = render_tender_operator_console_html()
    assert 'name="status_filter"' in html
    assert 'value="Подача заявок" selected' in html
    assert "searchParams.set('status_filter'" in html
    assert 'Совпадение с запросом' in html
    assert 'query_relevance' in html
    assert 'Срок подачи' in html
    assert 'стадия определена фильтром ЕИС' in html


def test_search_handoff_does_not_auto_run_llm_and_shows_progress(client):
    html = render_tender_operator_console_html()
    assert 'analyze_after_download: false' in html
    assert 'Получаем документацию' in html
    assert 'Анализ запускается отдельно' in html
