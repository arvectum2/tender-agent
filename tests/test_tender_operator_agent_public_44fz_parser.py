from src.modules.tender_operator_agent_demo.public_44fz_parser import (
    Public44FzSearchStatus,
    classify_public_search_response,
    extract_public_search_total_count,
    extract_reestr_number_from_44fz_card,
    parse_44fz_search_results,
)


SAMPLE_SEARCH_HTML = """<html>
<body>
<div class="registry-entry" data-id="123">
  <div class="registry-entry__header-mid__title">Электронный аукцион</div>
  <div class="registry-entry__header-mid__number">
    <a href="https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber=0888200000224000038">0888200000224000038</a>
  </div>
  <div class="registry-entry__body-title">Заказчик</div>
  <div class="registry-entry__body-value">ООО \"Примерный заказчик\"</div>
  <div class="registry-entry__body-title">Объект закупки</div>
  <div class="registry-entry__body-value">Поставка электротехнического оборудования</div>
  <div class="price-block__title">Начальная цена</div>
  <div class="price-block__value">1 250 000.00 RUB</div>
  <div class="data-block__title">Размещено</div>
  <div class="data-block__value">24.06.2026</div>
  <div class="data-block__title">Окончание подачи заявок</div>
  <div class="data-block__value">03.07.2026 10:00</div>
</div>
<div class="registry-entry" data-id="456">
  <div class="registry-entry__header-mid__title">Электронный аукцион</div>
  <div class="registry-entry__header-mid__number">
    <a href="https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber=0778200000224000055">0778200000224000055</a>
  </div>
  <div class="registry-entry__body-title">Заказчик</div>
  <div class="registry-entry__body-value">АО \"Кабельный завод\"</div>
  <div class="registry-entry__body-title">Объект закупки</div>
  <div class="registry-entry__body-value">Поставка кабельной продукции</div>
  <div class="price-block__title">Начальная цена</div>
  <div class="price-block__value">3 450 000.00 RUB</div>
</div>
</body>
</html>"""


def test_classify_parsed_html():
    assert classify_public_search_response(SAMPLE_SEARCH_HTML) == Public44FzSearchStatus.PARSED


def test_classify_empty_page():
    assert classify_public_search_response("") == Public44FzSearchStatus.EMPTY_RESULTS
    assert classify_public_search_response("   ") == Public44FzSearchStatus.EMPTY_RESULTS


def test_classify_captcha_page():
    html = "<html><body>Доступ ограничен. Пожалуйста, пройдите проверку captcha.</body></html>"
    assert classify_public_search_response(html) == Public44FzSearchStatus.CAPTCHA_OR_BLOCKED


def test_classify_js_heavy_page():
    html = "<html><body><noscript>Включите JavaScript</noscript></body></html>"
    assert classify_public_search_response(html) == Public44FzSearchStatus.JS_HEAVY


def test_classify_parsed_html_with_noscript_marker():
    html = f"{SAMPLE_SEARCH_HTML}<noscript>Для корректной работы интерфейса включите JavaScript только в браузере.</noscript>"
    assert classify_public_search_response(html) == Public44FzSearchStatus.PARSED


def test_classify_unsupported_layout():
    html = "<html><body>Страница не содержит распознаваемых элементов поиска</body></html>"
    assert classify_public_search_response(html) == Public44FzSearchStatus.UNSUPPORTED_LAYOUT


def test_extract_total_count_exact_value():
    html = """
    <div class="search-results__total">
      1 234 записей
    </div>
    """
    assert extract_public_search_total_count(html) == 1234


def test_extract_total_count_ignores_more_than_phrase():
    html = """
    <div class="search-results__total">
      более 150 000 записей
    </div>
    """
    assert extract_public_search_total_count(html) is None


def test_extract_total_count_prefers_hidden_download_csv_exact_value():
    html = """
    <a href="#" class="downLoad-search"
       onclick="downloadCsv('?searchString=%D0%BA%D0%B0%D0%B1%D0%B5%D0%BB%D1%8C', '159715')">
    </a>
    <div class="search-results__total">
      более 150 000 записей
    </div>
    """
    assert extract_public_search_total_count(html) == 159715


def test_parse_extracts_cards():
    cards = parse_44fz_search_results(SAMPLE_SEARCH_HTML)
    assert len(cards) > 0
    assert any("электротехнического" in c["title"].lower() for c in cards)
    assert any(c["notice_number"] == "0888200000224000038" for c in cards)
    assert any(c["deadline"] == "03.07.2026 10:00" for c in cards)
    assert any(c["procedure_type"] == "Электронный аукцион" for c in cards)


def test_extract_reestr_from_card():
    card_html = '<div><a href="https://zakupki.gov.ru/epz/order/notice/ea44/view.html?regNumber=0888200000224000038">0888200000224000038</a></div>'
    reestr = extract_reestr_number_from_44fz_card(card_html)
    assert reestr == "0888200000224000038"


def test_parse_handles_empty_page():
    cards = parse_44fz_search_results("")
    assert cards == []


def test_parse_handles_captcha_like_page():
    html = "<html><body>captcha проверка соединения</body></html>"
    status = classify_public_search_response(html)
    assert status == Public44FzSearchStatus.CAPTCHA_OR_BLOCKED
    cards = parse_44fz_search_results(html)
    assert cards == []


def test_parse_handles_js_heavy_page():
    html = "<html><body><noscript>Включите JavaScript</noscript></body></html>"
    status = classify_public_search_response(html)
    assert status == Public44FzSearchStatus.JS_HEAVY
    cards = parse_44fz_search_results(html)
    assert cards == []


def test_fallback_extraction_by_number():
    html = '<html><a href="/epz/order/notice/ea44/view.html?regNumber=0888200000224000038">link</a></html>'
    cards = parse_44fz_search_results(html)
    assert cards


def test_parser_does_not_use_token():
    import src.modules.tender_operator_agent_demo.public_44fz_parser as parser_module
    source = __import__(parser_module.__name__, fromlist=["token"])
    assert not hasattr(source, "token") or source.token is None
    assert not hasattr(parser_module, "ZAKUPKI_GOV_RU_SOAP_TOKEN")


def test_parse_prefers_procurement_notice_url_over_unrelated_absolute_asset():
    html = """<html><body>
    <div class="registry-entry">
      <a href="https://zakupki.gov.ru/rpt/cat02/zakupki-traffic.xlsx">traffic</a>
      <div class="registry-entry__header-mid__title">Электронный аукцион</div>
      <div class="registry-entry__header-mid__number">
        <a href="/epz/order/notice/ea20/view/common-info.html?regNumber=0262200000126000037">0262200000126000037</a>
      </div>
      <div class="registry-entry__body-title">Объект закупки</div>
      <div class="registry-entry__body-value">Разработка программного обеспечения</div>
    </div>
    </body></html>"""

    cards = parse_44fz_search_results(html)

    assert len(cards) == 1
    assert cards[0]["reestr_number"] == "0262200000126000037"
    assert cards[0]["source_url"] == (
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
        "?regNumber=0262200000126000037"
    )
