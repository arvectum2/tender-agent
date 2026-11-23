import pytest

from src.modules.tender_connectors.etp_gpb.parser import parse_list


def sample():
    return (b'<article data-testid="procedure-card"><a href="/procedures/etp/123-test/">'
            + "№ 123".encode() + b'</a><a href="/procedures/etp/123-test/">Test</a>'
            + "<div>Заказчики</div><div>Buyer</div><div>Начальная цена</div><div>100 ₽</div>".encode()
            + b'</article>')


def test_public_card():
    rows = parse_list(sample(), "https://etpgpb.ru/procedures/")
    assert rows[0]["external_id"] == "etp:123"
    assert rows[0]["customers_raw"] == "Buyer"
    assert rows[0]["price_raw"] == "100 ₽"
    assert rows[0]["verification"] == "PUBLIC_LIST_OBSERVATION_ONLY"


def test_duplicate_and_foreign_rejected():
    with pytest.raises(ValueError):
        parse_list(sample()*2, "https://etpgpb.ru/procedures/")
    with pytest.raises(ValueError):
        parse_list(sample(), "https://example.com/procedures/")


def test_gos_uuid_identity():
    raw = sample().replace(b"/procedures/etp/123-test/",
                           b"https://gos.etpgpb.ru/front/procedure/view/77a2fcac-8193-42e4-b561-f6cc11b680e8")
    assert parse_list(raw, "https://etpgpb.ru/procedures/")[0]["external_id"].startswith("gos:")


def test_update_date_is_separate_from_publication():
    raw = sample().replace(b"</article>", (
        "<div>Дата публикации</div><div>10 ноября 2026, 10:00 Z</div>"
        "<div>Дата обновления</div><div>13 ноября 2026, 12:00 Z</div></article>").encode())
    row = parse_list(raw, "https://etpgpb.ru/procedures/")[0]
    assert row["published_raw"] == "10 ноября 2026, 10:00 Z"
    assert row["updated_raw"] == "13 ноября 2026, 12:00 Z"


def test_numberless_native_etp_requires_audited_opt_in():
    # The source has an unambiguous pair of matching ETP numeric links, title,
    # and '-' instead of the formally published purchase-number label.
    raw = sample().replace("№ 123".encode(), b"-")
    with pytest.raises(ValueError, match="missing source identity"):
        parse_list(raw, "https://etpgpb.ru/procedures/")
    row = parse_list(raw, "https://etpgpb.ru/procedures/", allow_numberless_etp=True)[0]
    assert row["external_id"] == "etp:123"
    assert row["number_raw"] == "-"
    assert row["title"] == "Test"


def test_numberless_non_native_or_ambiguous_identity_rejected_even_with_opt_in():
    price_request = sample().replace("№ 123".encode(), b"-").replace(
        b"/procedures/etp/123-test/", b"/procedures/price_request/123-test/"
    )
    with pytest.raises(ValueError, match="missing source identity"):
        parse_list(price_request, "https://etpgpb.ru/procedures/", allow_numberless_etp=True)
    conflicting = sample().replace("№ 123".encode(), b"-").replace(
        b'<a href="/procedures/etp/123-test/">Test</a>',
        b'<a href="/procedures/etp/456-test/">Test</a>'
    )
    with pytest.raises(ValueError, match="ambiguous card identity"):
        parse_list(conflicting, "https://etpgpb.ru/procedures/", allow_numberless_etp=True)
