from __future__ import annotations

from datetime import datetime, timezone

from src.tender_research.providers.public_44fz_search import (
    Public44FzSearchProvider,
    PublicSearchStatus,
    PublicTenderSearchItem,
)


DETAIL_HTML = """
<div class="cardMainInfo__section">
  <span class="cardMainInfo__title">Объект закупки</span>
  <span class="cardMainInfo__content text-break">Поставка серверного оборудования</span>
</div>
<div class="cardMainInfo__section">
  <span class="cardMainInfo__title">Заказчик</span>
  <span class="cardMainInfo__content">
    <a href="/epz/organization/view/info.html?organizationCode=123" target="_blank">ГБУ Тестовый заказчик</a>
  </span>
</div>
<span class="cardMainInfo__title">Начальная цена</span>
<span class="cardMainInfo__content cost">1 234 567,89 ₽</span>
<div class="cardMainInfo__section col-6">
  <span class="cardMainInfo__title">Размещено</span>
  <span class="cardMainInfo__content">01.07.2026</span>
</div>
<div class="cardMainInfo__section">
  <span class="cardMainInfo__title">Окончание подачи заявок</span>
  <span class="cardMainInfo__content">09.07.2026 10:30</span>
</div>
<span class="greyText">ИНН: </span><span>7701234567</span><br/>
<span class="greyText">КПП: </span><span>770101001</span><br/>
"""


DOCUMENTS_HTML = """
<div class="attachmentsTabDocs">
  <div class="attachment row ">
    <div class="col clipText">
      <a data-modalup href="/epz/order/notice/signview/ep/listModal.html?reestrNumber=0373200000000000001&uid=sign-only">
        sign
      </a>
      <img alt="Adobe Acrobat Document" src="/epz/static/img/icons/type/pdf.svg"/>
      <span class="section__value">
        <a href="/44fz/filestore/public/1.0/download/priz/file.html?uid=UID001" title="Техническое задание.pdf">
          Техническое задание
        </a>
      </span>
    </div>
  </div>
  <div class="attachment row ">
    <div class="col clipText">
      <img alt="Microsoft Excel Document" src="/epz/static/img/icons/type/xlsx.svg"/>
      <span class="section__value">
        <a href="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=UID002" title="Расчет НМЦК.xlsx">
          Расчет НМЦК
        </a>
      </span>
    </div>
  </div>
</div>
"""


class FakeProvider(Public44FzSearchProvider):
    def __init__(self, pages: dict[str, dict[str, str | None]]):
        super().__init__(timeout_seconds=5, delay_seconds=0, bypass_proxy=True)
        self._pages = pages

    def _fetch_page(self, url: str) -> dict[str, str | None]:
        return self._pages[url]


def test_fetch_detail_parses_metadata_and_document_links():
    card_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=0373200000000000001"
    docs_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/documents.html?regNumber=0373200000000000001"
    provider = FakeProvider({
        card_url: {"status": PublicSearchStatus.SUCCESS, "html": DETAIL_HTML, "error": None},
        docs_url: {"status": PublicSearchStatus.SUCCESS, "html": DOCUMENTS_HTML, "error": None},
    })

    detail = provider.fetch_detail(
        PublicTenderSearchItem(
            registry_number="0373200000000000001",
            title="Search title",
            customer_name="Search customer",
            card_url=card_url,
            source_url="https://zakupki.gov.ru/epz/order/extendedsearch/results.html?pageNumber=1",
        )
    )

    assert detail.network_status == PublicSearchStatus.SUCCESS
    assert detail.title == "Поставка серверного оборудования"
    assert detail.customer_name == "ГБУ Тестовый заказчик"
    assert detail.customer_inn == "7701234567"
    assert detail.customer_kpp == "770101001"
    assert detail.publication_date == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert detail.application_deadline == datetime(2026, 7, 9, 10, 30, tzinfo=timezone.utc)
    assert float(detail.nmck_amount) == 1234567.89
    assert len(detail.document_links) == 2
    assert detail.document_links[0].url == "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=UID001"
    assert detail.document_links[0].file_name == "Техническое задание.pdf"
    assert detail.document_links[0].raw["uid"] == "UID001"
    assert detail.document_links[1].content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_detail_failure_does_not_erase_search_metadata():
    card_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=0373200000000000001"
    provider = FakeProvider({
        card_url: {"status": PublicSearchStatus.TIMEOUT, "html": None, "error": "timed out"},
    })

    detail = provider.fetch_detail(
        PublicTenderSearchItem(
            registry_number="0373200000000000001",
            title="Search title",
            customer_name="Search customer",
            publication_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            card_url=card_url,
        )
    )

    assert detail.network_status == PublicSearchStatus.TIMEOUT
    assert detail.title == "Search title"
    assert detail.customer_name == "Search customer"
    assert detail.publication_date == datetime(2026, 7, 1, tzinfo=timezone.utc)


def test_no_documents_returns_empty_list():
    card_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=0373200000000000001"
    docs_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/documents.html?regNumber=0373200000000000001"
    provider = FakeProvider({
        card_url: {"status": PublicSearchStatus.SUCCESS, "html": DETAIL_HTML, "error": None},
        docs_url: {"status": PublicSearchStatus.SUCCESS, "html": "<html><body>Нет файлов</body></html>", "error": None},
    })

    detail = provider.fetch_detail(card_url, registry_number="0373200000000000001")

    assert detail.network_status == PublicSearchStatus.SUCCESS
    assert detail.document_links == []


def test_detail_prefers_explicit_customer_requirements_over_placement_organization():
    card_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345678"
    docs_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    common_html = """
    <div class="cardMainInfo__section">
      <span class="cardMainInfo__title">Объект закупки</span>
      <span class="cardMainInfo__content">Оказание услуг</span>
    </div>
    <section class="blockInfo__section section">
      <span class="section__title">Организация, осуществляющая размещение</span>
      <span class="section__info">ГКУ Региональный центр закупок</span>
    </section>
    <div class="collapse__title_text">
      Требования заказчика&nbsp;&laquo;ГБУ &quot;Фактический заказчик&quot;&raquo;
    </div>
    """
    provider = FakeProvider({
        card_url: {"status": PublicSearchStatus.SUCCESS, "html": common_html, "error": None},
        docs_url: {"status": PublicSearchStatus.SUCCESS, "html": "<html></html>", "error": None},
    })

    detail = provider.fetch_detail(card_url, registry_number="0123456789012345678")

    assert detail.customer_name == 'ГБУ "Фактический заказчик"'


def test_detail_does_not_promote_placement_organization_when_customer_is_absent():
    card_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345679"
    docs_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345679"
    common_html = """
    <section class="blockInfo__section section">
      <span class="section__title">Организация, осуществляющая размещение</span>
      <span class="section__info">ГКУ Только организатор</span>
    </section>
    """
    provider = FakeProvider({
        card_url: {"status": PublicSearchStatus.SUCCESS, "html": common_html, "error": None},
        docs_url: {"status": PublicSearchStatus.SUCCESS, "html": "<html></html>", "error": None},
    })

    detail = provider.fetch_detail(card_url, registry_number="0123456789012345679")

    assert detail.customer_name is None
