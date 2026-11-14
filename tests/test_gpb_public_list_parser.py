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
