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



def _revision_attachment(name: str, uid: str) -> str:
    return f"""<div class="attachment row"><div class="col clipText"><span class="section__value"><a href="/44fz/filestore/public/1.0/download/priz/file.html?uid={uid}" title="{name}">{name}</a></span></div></div>"""


def _revision_block(*, version: int, state: str, published: str, attachments: list[tuple[str, str]]) -> str:
    attachment_html = "".join(_revision_attachment(name, uid) for name, uid in attachments)
    inactive_class = "inactiveElement" if state == "Недействующая" else ""
    return f"""
    <div class="row no-gutters notice-documents blockInfo__section">
      <a href="/epz/order/notice/printForm/viewByVersionNumber.html?regNumber=0123456789012345678&versionNumber={version}&qualifier=regNumberAndVersion">print</a>
      <div class="section__value docName"><span class="{inactive_class}">Извещение в ред. {version}</span></div>
      <div><div class="section__attrib">Размещено</div><div class="section__value {inactive_class}">{published} (МСК)</div></div>
      <div><div class="section__attrib">Редакция</div><div class="section__value {inactive_class}">{state}</div></div>
      <div class="attachmentsTabDocs">{attachment_html}</div>
    </div>
    """


def test_revision_selector_single_active_revision():
    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    page_html = _revision_block(
        version=1,
        state="Действующая",
        published="15.09.2026 10:00",
        attachments=[("Техническое задание.docx", "ACTIVE-1")],
    )

    links, revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert selection["status"] == "active_revision_selected"
    assert selection["requires_review"] is False
    assert len(revisions) == 1
    assert revisions[0].revision == 1
    assert revisions[0].active is True
    assert revisions[0].publication_timestamp == "15.09.2026 10:00 (МСК)"
    assert [item.raw["uid"] for item in links] == ["ACTIVE-1"]
    assert links[0].raw["revision"] == 1
    assert links[0].raw["revision_active"] is True


def test_revision_selector_excludes_inactive_overlapping_and_changed_files():
    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    page_html = "".join(
        [
            _revision_block(
                version=1,
                state="Недействующая",
                published="15.09.2026 09:00",
                attachments=[("Проект контракта.docx", "CONTRACT-OLD"), ("Общий файл.pdf", "SHARED")],
            ),
            _revision_block(
                version=2,
                state="Действующая",
                published="15.09.2026 11:00",
                attachments=[("Проект контракта.docx", "CONTRACT-NEW"), ("Общий файл.pdf", "SHARED")],
            ),
        ]
    )

    links, revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert selection["status"] == "active_revision_selected"
    assert [(item.revision, item.active) for item in revisions] == [(1, False), (2, True)]
    assert [item.raw["uid"] for item in links] == ["CONTRACT-NEW", "SHARED"]
    assert "CONTRACT-OLD" not in {item.raw["uid"] for item in links}
    assert {item.raw["uid"] for item in revisions[0].document_links} == {"CONTRACT-OLD", "SHARED"}
    assert {item.raw["uid"] for item in revisions[1].document_links} == {"CONTRACT-NEW", "SHARED"}


def test_revision_selector_fails_closed_on_ambiguous_active_state():
    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    page_html = "".join(
        [
            _revision_block(version=1, state="Действующая", published="15.09.2026 09:00", attachments=[("a.pdf", "A")]),
            _revision_block(version=2, state="Действующая", published="15.09.2026 11:00", attachments=[("b.pdf", "B")]),
        ]
    )

    links, revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert links == []
    assert len(revisions) == 2
    assert selection["status"] == "ambiguous_revision_state"
    assert selection["requires_review"] is True


def test_revision_selector_fails_closed_when_active_binding_is_missing():
    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    page_html = "".join(
        [
            _revision_block(version=1, state="Недействующая", published="15.09.2026 09:00", attachments=[("old.pdf", "OLD")]),
            _revision_block(version=2, state="Действующая", published="15.09.2026 11:00", attachments=[]),
        ]
    )

    links, _revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert links == []
    assert selection["status"] == "active_revision_attachment_binding_missing"
    assert selection["requires_review"] is True


def test_case14_documents_page_selects_only_revision_two():
    from pathlib import Path

    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    import hashlib

    fixture = Path(__file__).parents[1] / "fixtures" / "eis" / "case14_documents_page_0194200000526005052.html"
    fixture_bytes = fixture.read_bytes()
    assert hashlib.sha256(fixture_bytes).hexdigest() == "ef21176d9480e4b15d8a5a966e5cf8b80aa7fbc581405487fb9d0f908fd930bb"
    page_html = fixture_bytes.decode("utf-8")
    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0194200000526005052"

    links, revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert selection["status"] == "active_revision_selected"
    assert selection["active_revision"]["revision"] == 2
    assert selection["active_revision"]["publication_timestamp"] == "14.09.2026 23:01 (МСК)"
    assert [(item.revision, item.active) for item in revisions] == [(1, False), (2, True)]
    assert len(links) == 6
    current_uids = {item.raw["uid"] for item in links}
    assert "01A0A1820C5D78658254DD3624705FAF" in current_uids
    assert "01A09F45FB0E7725B1DFA36E795BC4D0" not in current_uids
    assert all(item.raw["revision"] == 2 for item in links)
    assert all(item.raw["revision_active"] is True for item in links)



def test_revision_selector_fails_closed_when_revision_controls_are_exposed_but_unparsed():
    from src.tender_research.providers.public_44fz_search import _select_current_revision_document_links

    page_url = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0123456789012345678"
    page_html = """
    <input type="checkbox" class="inactive-redaction-toggle">
    <div class="attachment row"><div><a href="/44fz/filestore/public/1.0/download/priz/file.html?uid=UNBOUND" title="file.pdf">file</a></div></div>
    """

    links, revisions, selection = _select_current_revision_document_links(page_html, page_url)

    assert links == []
    assert revisions == []
    assert selection["status"] == "revision_binding_unparsed"
    assert selection["requires_review"] is True
