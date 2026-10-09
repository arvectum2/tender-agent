"""Legacy EAT and Moscow portal field API remains backward compatible."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.modules.tender_connectors.eat.parser import (
    _parse_datetime as eat_date,
)
from src.modules.tender_connectors.eat.parser import (
    _pick_nested as eat_pick,
)
from src.modules.tender_connectors.mos_portal.parser import (
    _parse_datetime as mos_date,
)
from src.modules.tender_connectors.mos_portal.parser import (
    _pick_nested as mos_pick,
)
from src.modules.tender_connectors.shared_fields import (
    parse_portal_datetime,
    pick_nested,
)


@pytest.mark.parametrize("getter", [pick_nested, eat_pick, mos_pick])
def test_dotted_nested_selector_array_semantics(getter):
    source = {"root": [{"value": "  Санкт-Петербург  "}, {"value": "Москва"}]}
    assert getter(source, ["missing", "root.0.value"]) == "Санкт-Петербург"
    assert getter(source, ["root.2.value"]) is None
    assert getter(source, ["root.bad.value"]) is None


@pytest.mark.parametrize("getter", [parse_portal_datetime, eat_date, mos_date])
def test_portal_dates_preserve_formats(getter):
    assert getter("2026-06-13T15:30:00Z") == datetime(2026, 6, 13, 15, 30, tzinfo=UTC)
    assert getter("13.06.2026 15:30") == datetime(2026, 6, 13, 15, 30)  # noqa: DTZ001
    assert getter("13.06.2026") == datetime(2026, 6, 13)  # noqa: DTZ001
    assert getter("not-date") is None
