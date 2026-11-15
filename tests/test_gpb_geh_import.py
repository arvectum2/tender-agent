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
