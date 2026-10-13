"""Original B2B-Center lot card ID is not automatically a unique procedure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.tender_research.corporate_procedure_identity import (
    resolve_b2b_center_procedure_identity,
)

DATA = json.loads((
    Path(__file__).resolve().parents[1]
    / "docs/roadmap/b2b_parent_lot_original_audit_2026-10-14.json"
).read_text(encoding="utf-8"))
LOT_URL = DATA["original_pages"][0]["source_url"]
PARENT_URL = LOT_URL.replace("tender-4632699/", "tender-4632682/")


def checked(url: str, body: str, *, digest: str | None = None):
    raw = body.encode("utf-8")
    return resolve_b2b_center_procedure_identity(
        original_card_url=url,
        original_html=raw,
        expected_sha256=digest or hashlib.sha256(raw).hexdigest(),
    )


def test_original_lot_page_references_existing_parent_and_does_not_create_second_procedure():
    lot = checked(
        LOT_URL,
        "<html><head><script>ignored 123</script></head><body>"
        "<h1>Лот № 1 Предварительного квалификационного отбора № 4632682</h1>"
        "</body></html>",
    )
    parent = checked(
        PARENT_URL,
        "<h1>Предварительный квалификационный отбор № 4632682</h1>",
    )
    assert (lot.state, lot.card_number, lot.procedure_number, lot.lot_number) == (
        "PARENT_LOT_CONFIRMED", "4632699", "4632682", "1",
    )
    assert parent.state == "DIRECT_PROCEDURE_CONFIRMED"
    assert len({lot.unique_procedure_key, parent.unique_procedure_key}) == 1
    assert parent.unique_procedure_key == "b2b-center:4632682"
    assert lot.bid_ready is False and parent.bid_ready is False


def test_exact_original_receipt_and_exclusion_categories_remain_unpromoted():
    original = DATA["original_pages"]
    assert len(original) == 3
    lot, archived, monitoring = original
    assert lot["card_number"] == "4632699"
    assert lot["parent_procedure_number"] == "4632682"
    assert lot["new_unique_qualified_leads_added"] == 0
    assert archived["source_status"] == "ARCHIVED"
    assert archived["new_unique_qualified_leads_added"] == 0
    assert monitoring["procedure_type"] == "PRICE_MONITORING"
    assert monitoring["new_unique_qualified_leads_added"] == 0
    for record in original:
        assert record["direct_http_status"] == 200
        assert len(record["html_sha256"]) == 64
        assert record["retrieved_bytes"] > 30000
    assert DATA["goal_15_to_20_simultaneously_qualified_live_software_leads_met"] is False


@pytest.mark.parametrize("body", [
    "<html>Разработка сайтов, размещение закупок — категория, не извещение</html>",
    "<html><script>Лот № 1 Предварительного квалификационного отбора № 4632682</script></html>",
    "<h1>Предварительный квалификационный отбор № 4632683</h1>",
    ("<h1>Лот № 1 Предварительного квалификационного отбора № 4632682</h1>"
     "<h2>Лот № 2 Предварительного квалификационного отбора № 4632684</h2>"),
])
def test_missing_script_only_or_conflicting_procedure_does_not_count(body):
    result = checked(LOT_URL, body)
    assert result.state == "REVIEW_REQUIRED"
    assert result.unique_procedure_key is None
    assert result.bid_ready is False


@pytest.mark.parametrize("url", [
    "https://zakupki.kontur.ru/4632699_40",
    "http://www.b2b-center.ru/market/site/tender-4632699/",
    "https://www.b2b-center.ru/search/industry/razrabotka-sajtov/",
    "https://www.b2b-center.ru/market/site/tender-4632699/?tracking=1",
])
def test_non_original_or_catalog_urls_do_not_count(url):
    x = checked(
        url,
        "<h1>Лот № 1 Предварительного квалификационного отбора № 4632682</h1>",
    )
    assert x.state == "REVIEW_REQUIRED" and x.unique_procedure_key is None


def test_unrelated_sidebar_lot_reference_cannot_override_main_heading():
    x = checked(
        LOT_URL,
        "<h1>Объявление о консультационных услугах № 4632699</h1>"
        "<aside>Рекомендуем: Лот № 1 Предварительного квалификационного отбора № 4632682</aside>",
    )
    assert (x.state, x.reason, x.unique_procedure_key) == (
        "REVIEW_REQUIRED", "procedure_identity_unverified", None,
    )


def test_source_sha_mismatch_abstains_even_with_matching_lot_reference():
    x = checked(
        LOT_URL,
        "<h1>Лот № 1 Предварительного квалификационного отбора № 4632682</h1>",
        digest="0" * 64,
    )
    assert (x.state, x.reason, x.unique_procedure_key) == (
        "REVIEW_REQUIRED", "source_bytes_sha256_mismatch", None,
    )


def test_invalid_or_missing_receipt_never_countable():
    x = checked(LOT_URL, "<h1>Лот № 1 Предварительного квалификационного отбора № 4632682</h1>", digest="invalid")
    assert x.state == "REVIEW_REQUIRED"
    assert x.unique_procedure_key is None
