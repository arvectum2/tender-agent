import pytest

from scripts.research.source_catalog import (
    SOURCES,
    Coverage,
    Evidence,
    SourceIdentity,
)
from scripts.research.source_catalog import (
    classify_coverage as _classify_coverage,
)


def classify_coverage(**kwargs):
    return _classify_coverage(source="etp_gpb", namespaces=("etp", "gos"), **kwargs)


def test_gpb_namespaces_and_customer_scopes():
    etp = SourceIdentity("etp_gpb", "etp", "123")
    price = SourceIdentity("etp_gpb", "price_request", "123")
    assert etp.key != price.key
    assert etp.key == SourceIdentity("etp_gpb", "etp", "123").key
    assert "geh" not in SOURCES
    with pytest.raises(ValueError):
        SourceIdentity("geh", "etp", "123")


def test_sources_without_verified_listing_not_onboarded():
    for source in ("tek_torg", "eat"):
        assert SOURCES[source].fresh == Evidence.UNVERIFIED
        with pytest.raises(ValueError):
            SourceIdentity(source, "procedure", "123")
    assert SOURCES["mos_portal"].documents == Evidence.UNVERIFIED


@pytest.mark.parametrize("value", ["", " abc", "abc ", "a\nb", "x" * 257, None])
def test_identity_refuses_malformed_values(value):
    with pytest.raises(ValueError):
        SourceIdentity("etp_gpb", "etp", value)


def test_partial_or_error_not_empty_success():
    assert (
        classify_coverage(reported_count=0, observed_ids=(), all_pages_verified=True)
        == Coverage.PARTIAL
    )
    assert (
        classify_coverage(
            reported_count=0,
            observed_ids=(),
            all_pages_verified=True,
            explicit_empty=True,
        )
        == Coverage.COMPLETE
    )
    assert (
        classify_coverage(
            reported_count=0,
            observed_ids=(),
            all_pages_verified=True,
            explicit_empty=True,
            source_error=True,
        )
        == Coverage.FAILED
    )


def test_coverage_requires_exact_unique_count():
    a = SourceIdentity("etp_gpb", "etp", "1")
    b = SourceIdentity("etp_gpb", "gos", "1")
    for count, items, pages in (
        (2, (a, a), True),
        (3, (a, b), True),
        (2, (a, b), False),
        (None, (a, b), True),
        (True, (a,), True),
    ):
        assert (
            classify_coverage(
                reported_count=count, observed_ids=items, all_pages_verified=pages
            )
            == Coverage.PARTIAL
        )
    assert (
        classify_coverage(
            reported_count=2, observed_ids=(a, b), all_pages_verified=True
        )
        == Coverage.COMPLETE
    )
    c = SourceIdentity("sibur", "procedure", "1")
    assert (
        classify_coverage(
            reported_count=2, observed_ids=(a, c), all_pages_verified=True
        )
        == Coverage.PARTIAL
    )


def test_wrong_request_scope_fails_closed():
    wrong = SourceIdentity("etp_gpb", "price_request", "1")
    assert (
        classify_coverage(
            reported_count=1, observed_ids=(wrong,), all_pages_verified=True
        )
        == Coverage.PARTIAL
    )
    with pytest.raises(ValueError):
        _classify_coverage(
            source="tek_torg",
            namespaces=("procedure",),
            reported_count=0,
            observed_ids=(),
            all_pages_verified=True,
            explicit_empty=True,
        )
    with pytest.raises(ValueError):
        classify_coverage(
            reported_count=0,
            observed_ids=(),
            all_pages_verified="yes",
            explicit_empty=True,
        )
