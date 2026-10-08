from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.tender_research.historical_prices import build_historical_price_range
from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository


class FakeRetriever:
    def __init__(self, hits_by_query: dict[str, list[RagSearchHit]]) -> None:
        self.hits_by_query = hits_by_query

    def search_all_documents(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RagSearchHit]:
        return list(self.hits_by_query.get(query, []))


def _hit(tender, *, chunk_id: str, score: float = 0.03) -> RagSearchHit:
    return RagSearchHit(
        chunk_id=chunk_id,
        score=score,
        registry_number=tender.registry_number,
        tender_id=tender.id,
        tender_title=tender.title,
        customer_name=tender.customer_name,
        document_id=f"doc-{chunk_id}",
        file_name="nmck.txt",
        chunk_index=0,
        preview=tender.title,
        text=tender.title,
    )


def _raw(
    *,
    name: str,
    quantity: float,
    unit: str,
    okpd: str = "27.32.13.110",
) -> dict:
    return {
        "positions": [
            {
                "name": name,
                "quantity": quantity,
                "unit": unit,
                "okpd2_code": okpd,
            }
        ],
        "okpd2_codes": [{"code": okpd}],
    }


def _tender(
    repo: TenderRepository,
    *,
    external_id: str,
    registry_number: str,
    title: str,
    publication_date: datetime,
    nmck: float,
    quantity: float,
    unit: str = "м",
    currency: str = "RUB",
    okpd: str = "27.32.13.110",
):
    return repo.upsert_tender(
        {
            "source": "eis",
            "external_id": external_id,
            "registry_number": registry_number,
            "title": title,
            "publication_date": publication_date,
            "nmck_amount": nmck,
            "currency": currency,
            "eis_url": f"https://zakupki.gov.ru/{registry_number}",
            "raw_payload": _raw(
                name="Кабель силовой ВВГнг-LS",
                quantity=quantity,
                unit=unit,
                okpd=okpd,
            ),
        }
    )


def test_historical_price_range_normalizes_single_position_nmck_per_quantity(session):
    repo = TenderRepository(session)
    seed_date = datetime(2026, 10, 1, tzinfo=UTC)
    seed = _tender(
        repo,
        external_id="seed-price",
        registry_number="0570000000000000001",
        title="Поставка кабеля силового ВВГнг-LS",
        publication_date=seed_date,
        nmck=150_000,
        quantity=1000,
    )
    first = _tender(
        repo,
        external_id="hist-1",
        registry_number="0570000000000000002",
        title="Кабель силовой ВВГнг-LS для объекта",
        publication_date=seed_date - timedelta(days=30),
        nmck=120_000,
        quantity=1000,
    )
    second = _tender(
        repo,
        external_id="hist-2",
        registry_number="0570000000000000003",
        title="Поставка силового кабеля ВВГнг-LS",
        publication_date=seed_date - timedelta(days=60),
        nmck=280_000,
        quantity=2000,
    )
    session.commit()

    positions_query = "Кабель силовой ВВГнг-LS"
    retriever = FakeRetriever(
        {
            seed.title: [
                _hit(first, chunk_id="h1"),
                _hit(second, chunk_id="h2"),
            ],
            positions_query: [
                _hit(first, chunk_id="h1-pos"),
                _hit(second, chunk_id="h2-pos"),
            ],
        }
    )

    result = build_historical_price_range(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.state == "AVAILABLE"
    assert result.range is not None
    assert result.range.basis == "SINGLE_POSITION_UNIT_NMCK"
    assert result.range.unit == "м"
    assert result.range.minimum == 120.0
    assert result.range.median == 130.0
    assert result.range.maximum == 140.0
    assert result.range.sample_count == 2
    assert result.seed_comparable_amount == 150.0
    assert result.seed_orientation == "ABOVE_RANGE"
    assert result.is_forecast is False
    assert result.commercial_commitment is False
    assert all(item.evidence for item in result.observations)
    assert all(
        item.evidence[0].source_url
        and item.evidence[0].source_ref.endswith(":nmck_amount")
        for item in result.observations
    )


def test_historical_price_range_rejects_future_currency_and_unit_incomparables(session):
    repo = TenderRepository(session)
    seed_date = datetime(2026, 10, 1, tzinfo=UTC)
    seed = _tender(
        repo,
        external_id="seed-guards",
        registry_number="0570000000000000011",
        title="Поставка кабеля силового",
        publication_date=seed_date,
        nmck=100_000,
        quantity=1000,
    )
    future = _tender(
        repo,
        external_id="future",
        registry_number="0570000000000000012",
        title="Кабель силовой",
        publication_date=seed_date + timedelta(days=1),
        nmck=90_000,
        quantity=1000,
    )
    usd = _tender(
        repo,
        external_id="usd",
        registry_number="0570000000000000013",
        title="Кабель силовой медный",
        publication_date=seed_date - timedelta(days=10),
        nmck=1000,
        quantity=1000,
        currency="USD",
    )
    wrong_unit = _tender(
        repo,
        external_id="wrong-unit",
        registry_number="0570000000000000014",
        title="Кабель силовой ВВГ",
        publication_date=seed_date - timedelta(days=20),
        nmck=100_000,
        quantity=1000,
        unit="кг",
    )
    session.commit()
    hits = [
        _hit(future, chunk_id="f"),
        _hit(usd, chunk_id="u"),
        _hit(wrong_unit, chunk_id="w"),
    ]
    retriever = FakeRetriever(
        {
            seed.title: hits,
            "Кабель силовой ВВГнг-LS": hits,
        }
    )

    result = build_historical_price_range(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.state == "INSUFFICIENT_EVIDENCE"
    assert result.range is None
    assert result.observations == []
    assert result.rejected_counts["not_historical"] >= 1
    assert result.rejected_counts["currency_mismatch_or_unknown"] >= 1
    assert result.rejected_counts["quantity_unit_basis_incomparable"] >= 1


def test_historical_price_range_fails_closed_when_seed_quantity_or_unit_unknown(
    session,
):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-no-basis",
            "registry_number": "0570000000000000021",
            "title": "Поставка серверов",
            "publication_date": datetime(2026, 10, 1, tzinfo=UTC),
            "nmck_amount": 2_000_000,
            "currency": "RUB",
            "raw_payload": {"positions": [{"name": "Сервер"}]},
        }
    )
    session.commit()

    result = build_historical_price_range(
        repo,
        FakeRetriever({}),
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.state == "INSUFFICIENT_EVIDENCE"
    assert result.rejected_counts == {"seed_quantity_or_unit_unknown": 1}
    assert result.is_forecast is False
    assert result.commercial_commitment is False


def test_historical_price_api_uses_existing_data_platform_retriever(
    client,
    session,
    monkeypatch,
):
    from src.modules.historical_prices import router as route_module

    repo = TenderRepository(session)
    seed_date = datetime(2026, 10, 1, tzinfo=UTC)
    seed = _tender(
        repo,
        external_id="seed-api",
        registry_number="0570000000000000031",
        title="Поставка кабеля силового ВВГнг-LS",
        publication_date=seed_date,
        nmck=150_000,
        quantity=1000,
    )
    first = _tender(
        repo,
        external_id="api-h1",
        registry_number="0570000000000000032",
        title="Кабель силовой ВВГнг-LS",
        publication_date=seed_date - timedelta(days=10),
        nmck=120_000,
        quantity=1000,
    )
    second = _tender(
        repo,
        external_id="api-h2",
        registry_number="0570000000000000033",
        title="Поставка кабеля ВВГнг-LS",
        publication_date=seed_date - timedelta(days=20),
        nmck=260_000,
        quantity=2000,
    )
    session.commit()
    fake = FakeRetriever(
        {
            seed.title: [
                _hit(first, chunk_id="a1"),
                _hit(second, chunk_id="a2"),
            ],
            "Кабель силовой ВВГнг-LS": [
                _hit(first, chunk_id="p1"),
                _hit(second, chunk_id="p2"),
            ],
        }
    )

    class _ClientContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        route_module,
        "build_data_platform_client",
        lambda _config: _ClientContext(),
    )
    monkeypatch.setattr(
        route_module,
        "DataPlatformRagRetriever",
        lambda _repo, _client: fake,
    )

    response = client.get(
        f"/api/tender-research/historical-prices/{seed.registry_number}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "AVAILABLE"
    assert payload["range"]["basis"] == "SINGLE_POSITION_UNIT_NMCK"
    assert payload["is_forecast"] is False


def test_historical_price_range_rejects_multi_position_basket_with_different_items(
    session,
):
    repo = TenderRepository(session)
    seed_date = datetime(2026, 10, 1, tzinfo=UTC)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-basket",
            "registry_number": "0570000000000000041",
            "title": "Поставка кабеля и автоматических выключателей",
            "publication_date": seed_date,
            "nmck_amount": 500_000,
            "currency": "RUB",
            "raw_payload": {
                "positions": [
                    {"name": "Кабель силовой", "quantity": 1000, "unit": "м"},
                    {
                        "name": "Выключатель автоматический",
                        "quantity": 20,
                        "unit": "шт",
                    },
                ],
                "okpd2_codes": [{"code": "27.32.13.110"}],
            },
        }
    )
    candidate = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "bad-basket",
            "registry_number": "0570000000000000042",
            "title": "Поставка кабеля и электротехнических изделий",
            "publication_date": seed_date - timedelta(days=30),
            "nmck_amount": 420_000,
            "currency": "RUB",
            "raw_payload": {
                "positions": [
                    {"name": "Кабель силовой", "quantity": 1000, "unit": "м"},
                    {"name": "Розетка силовая", "quantity": 20, "unit": "шт"},
                ],
                "okpd2_codes": [{"code": "27.32.13.110"}],
            },
        }
    )
    session.commit()
    position_query = "Кабель силовой Выключатель автоматический"
    retriever = FakeRetriever(
        {
            seed.title: [_hit(candidate, chunk_id="basket-subject")],
            position_query: [_hit(candidate, chunk_id="basket-position")],
        }
    )

    result = build_historical_price_range(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.state == "INSUFFICIENT_EVIDENCE"
    assert result.observations == []
    assert result.rejected_counts["quantity_unit_basis_incomparable"] == 1
