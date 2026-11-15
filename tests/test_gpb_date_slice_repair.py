from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.research.repair_gpb_date_slices import inspect, slice_url, split


def test_exact_nonoverlapping_slice_bounds():
    a,b=date(2024,8,1),date(2024,8,31)
    x,y=split(a,b)
    assert x[0]==a and y[1]==b and x[1]+timedelta(days=1)==y[0]
    q=parse_qs(urlsplit(slice_url(*y,2)).query)
    assert q["procedure[accepted_from]"]==["17.08.2024"]
    assert q["procedure[accepted_to]"]==["31.08.2024"]
    assert q["procedure[stage][0]"]==["completed"]
    assert split(a,a)==[]
    with pytest.raises(ValueError):
        slice_url(a,date(2024,9,1),1)


def test_explicit_empty_scope_only():
    a=date(2024,8,1)
    scope,rows=inspect("0 предложений".encode(),a,a,1)
    assert scope["reported_total"]==0 and rows==[]
    with pytest.raises(ValueError):
        inspect("0 предложений".encode(),a,a,2)
    with pytest.raises(ValueError):
        inspect(b"no source count",a,a,1)
