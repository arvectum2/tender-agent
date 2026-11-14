import pytest

from src.modules.tender_connectors.etp_gpb.documents import (
    parse_document_links,
    valid_document_url,
)

URL = "https://etp.gpb.ru/file/get/t/LotDocuments/id/123/name/abcd.123"
DETAIL = "https://etpgpb.ru/procedures/etp/123-example/"


def test_exact_published_anchor_not_footer():
    raw = (f'<a href="https://cdn-open.etpgpb.ru/docs/1/a.pdf">Policy</a>'
           f'<a class="procedureDocItem__title vTxt" href="{URL}">ТЗ.docx</a>').encode()
    rows = parse_document_links(raw, detail_url=DETAIL, external_id="etp:123")
    assert len(rows) == 1
    assert rows[0]["original_filename"] == "ТЗ.docx"
    assert rows[0]["document_url"] == URL


def test_reject_foreign_and_mismatched_detail():
    assert not valid_document_url(URL.replace("etp.gpb.ru", "example.com"))
    assert not valid_document_url(URL + "?token=a")
    with pytest.raises(ValueError):
        parse_document_links(b"", detail_url=DETAIL, external_id="etp:124")


def test_price_request_link():
    assert valid_document_url("https://etp.gpb.ru/file/get/t/PriceOrderDocument/id/123/m/nsi/name/abcd.123")


def test_root_link_is_unavailable_not_downloadable():
    from src.modules.tender_connectors.etp_gpb.documents import parse_document_entries

    raw = (f'<a class="procedureDocItem__title" href="{URL}">ТЗ.docx</a>'
           '<a class="procedureDocItem__title" href="https://etp.gpb.ru/">Жалоба.doc</a>').encode()
    links, unavailable = parse_document_entries(raw, detail_url=DETAIL, external_id="etp:123")
    assert len(links) == 1
    assert unavailable == [{"original_filename": "Жалоба.doc", "verification": "LABEL_ONLY_ROOT_LINK"}]
