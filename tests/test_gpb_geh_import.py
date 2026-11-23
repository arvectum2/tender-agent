from datetime import UTC, datetime
from decimal import Decimal

import pytest

from scripts.research.import_gpb_geh_snapshots import (
    normalize,
    parse_date,
    price_for,
    stage_for,
)

URL = "https://etpgpb.ru/procedures/?procedure%5Bsection%5D%5B0%5D=geh_group&procedure%5Bstage%5D%5B0%5D=completed"


def test_russian_utc_and_price():
    assert parse_date("13 ноября 2026, 07:00 Z").tzinfo == UTC
    assert price_for("4 080 764,40 ₽") == Decimal("4080764.40")
    assert price_for("Цена не указана") is None
    with pytest.raises(ValueError):
        parse_date("13 ноября 2026, 07:00")


def test_source_stage_scope():
    assert stage_for(URL) == "completed"
    with pytest.raises(ValueError):
        stage_for(URL.replace("geh_group", "other"))


def test_never_treat_future_deadline_as_completed():
    row = {"source_url": URL, "published_raw": "9 ноября 2025, 12:30 Z",
           "deadline_raw": "16 ноября 2026, 05:30 Z"}
    with pytest.raises(ValueError, match="stage/date"):
        normalize({"observation": row, "observed_at": datetime(2025, 11, 14, tzinfo=UTC).isoformat()})


def test_official_single_decimal_rubles_normalize_without_rounding():
    for value, expected in (("301,6 ₽", "301.6"), ("6435,5 ₽", "6435.5"), ("9727,6 ₽", "9727.6")):
        assert price_for(value) == Decimal(expected)
    for value in ("301, ₽", "301,625 ₽", "-301,5 ₽", "1.5 ₽", " ₽"):
        with pytest.raises(ValueError, match="unexpected price"):
            price_for(value)


def _verified_card(number="-"):
    return {"source": "etp_gpb", "external_id": "etp:1123151",
            "number_raw": number,
            "title": "КО №2658/КО - Поставка оборудования для модернизации ПТК АСУ ТП",
            "source_url": URL, "source_sha256": "a" * 64,
            "verification": "PUBLIC_LIST_OBSERVATION_ONLY",
            "published_raw": "27 мая 2025, 14:20 Z",
            "deadline_raw": "04 июня 2025, 07:00 Z",
            "price_raw": "84 182 720,76 ₽",
            "detail_url": "https://etpgpb.ru/procedures/etp/1123151-audited/"}


def test_numberless_etp_preserves_unknown_purchase_number_as_null():
    row = normalize({"observation": _verified_card(),
                     "observed_at": datetime(2026, 11, 23, tzinfo=UTC).isoformat()})
    assert row["external_id"] == "etp:1123151"
    assert row["purchase_number"] is None
    assert row["raw_payload"]["observation"]["number_raw"] == "-"
    assert row["nmck_amount"] == 84182720.76


def test_source_publication_after_deadline_must_remain_review():
    card = _verified_card(number="№ 1123151")
    card["published_raw"] = "21 октября 2026, 04:28 Z"
    card["deadline_raw"] = "15 сентября 2026, 01:00 Z"
    with pytest.raises(ValueError, match="inconsistent source dates"):
        normalize({"observation": card, "observed_at":
                   datetime(2026, 11, 23, tzinfo=UTC).isoformat()})
