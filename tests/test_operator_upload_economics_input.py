import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy
from src.modules.tender_operator_agent_demo.operator_upload_economics_input import (
    _sanitize_delay_days,
    _sanitize_percent,
)


def test_exact_legacy_function_facades():
    assert legacy._sanitize_percent is _sanitize_percent
    assert legacy._sanitize_delay_days is _sanitize_delay_days


@pytest.mark.parametrize("value, expected", [(None, 15.0), (0, 0.0), (95, 95.0), (1.256, 1.26)])
def test_margin_valid_bounds_and_precision(value, expected):
    assert _sanitize_percent(value, default=15, field_name="target_margin") == expected


@pytest.mark.parametrize("value", [-0.1, 95.01])
def test_margin_out_of_bounds_rejected(value):
    with pytest.raises(HTTPException) as ex:
        _sanitize_percent(value, default=15, field_name="margin")
    assert ex.value.status_code == 400


@pytest.mark.parametrize("value, expected", [(None, 45), (0, 0), (365, 365)])
def test_delay_bounds(value, expected):
    assert _sanitize_delay_days(value, default=45) == expected


@pytest.mark.parametrize("value", [-1, 366])
def test_delay_invalid(value):
    with pytest.raises(HTTPException) as ex:
        _sanitize_delay_days(value, default=45)
    assert ex.value.status_code == 400
