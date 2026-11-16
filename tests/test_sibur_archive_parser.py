import json

import pytest

from src.modules.tender_connectors.sibur.archive_parser import (
    CATEGORIES,
    archive_page,
    archive_url,
)
from src.modules.tender_connectors.sibur.parser import HEADERS


def fixture(category="107", last=1075):
    row=["1234567/1","Equipment","Spec","Request","14.11.2026","19.11.2026 09:00",
         "Buyer","Прием предложений завершен","PRIVATE NAME","PRIVATE PHONE","PRIVATE EMAIL",
         CATEGORIES[category][1],'<a href="/upload/tmp/example/a.pdf">Doc</a>']
    head="<tr>"+"".join(f"<th>{v}</th>" for v in HEADERS)+"</tr>"
    body="<tr>"+"".join(f"<td>{v}</td>" for v in row)+"</tr>"
    return json.dumps({"content":'<table class="table__table">'+head+body+"</table>",
                       "pagination":'<a class="_current pagination__items-item">1</a>'
                                    +f'<a class="pagination__items-item">{last}</a>'}).encode()


def test_archive_source_large_paginator_and_privacy():
    result=archive_page(fixture(), "107", 1)
    assert result.last_page==1075
    row=result.records[0]
    assert row["source_url"]==archive_url("107",1)
    assert "/archive/" in row["source_url"]
    assert "PRIVATE" not in str(row)
    assert row["status_raw"]=="Прием предложений завершен"
    assert row["documentation_urls"]==["https://www.sibur.ru/upload/tmp/example/a.pdf"]


def test_filter_and_page_mismatch():
    with pytest.raises(ValueError,match="category"):
        archive_page(fixture(), "108", 1)
    with pytest.raises(ValueError,match="pagination"):
        archive_page(fixture(), "107", 2)
    with pytest.raises(ValueError):
        archive_url("unverified",1)
