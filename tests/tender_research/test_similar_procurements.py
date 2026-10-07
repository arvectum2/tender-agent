from __future__ import annotations

from src.tender_research.rag.search_types import RagSearchHit
from src.tender_research.repository import TenderRepository
from src.tender_research.similar_procurements import find_similar_procurements


class FakeRetriever:
    def __init__(self, hits_by_query: dict[str, list[RagSearchHit]]) -> None:
        self.hits_by_query = hits_by_query
        self.queries: list[tuple[str, int]] = []

    def search_all_documents(
        self, query: str, *, limit: int = 10
    ) -> list[RagSearchHit]:
        self.queries.append((query, limit))
        return list(self.hits_by_query.get(query, []))


def _hit(tender, *, chunk_id: str, text: str, score: float = 0.031) -> RagSearchHit:
    return RagSearchHit(
        chunk_id=chunk_id,
        score=score,
        registry_number=tender.registry_number,
        tender_id=tender.id,
        tender_title=tender.title,
        customer_name=tender.customer_name,
        document_id=f"doc-{chunk_id}",
        file_name="technical_spec.txt",
        chunk_index=0,
        preview=text[:280],
        text=text,
    )


def _raw(
    *,
    position: str,
    requirement: str,
    okpd: str,
) -> dict:
    return {
        "positions": [{"name": position, "okpd2_code": okpd}],
        "requirements": [{"title": "Требование", "detail": requirement}],
        "okpd2_codes": [{"code": okpd}],
    }


def test_similar_procurements_explains_all_available_signals_and_reuses_retrieval(
    session,
):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-055",
            "registry_number": "0550000000000000001",
            "title": "Поставка дизельного топлива для автотранспорта",
            "customer_name": "ГБУ Автопарк",
            "customer_inn": "7701000001",
            "raw_payload": _raw(
                position="Топливо дизельное летнее",
                requirement="Экологический класс К5, ГОСТ 32511-2013",
                okpd="19.20.21.300",
            ),
        }
    )
    analogue = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "analogue-055",
            "registry_number": "0550000000000000002",
            "title": "Дизельное топливо для служебного автотранспорта",
            "customer_name": "ГБУ Автопарк",
            "customer_inn": "7701000001",
            "raw_payload": _raw(
                position="Топливо дизельное",
                requirement="Дизельное топливо экологического класса К5 по ГОСТ 32511-2013",
                okpd="19.20.21.300",
            ),
        }
    )
    session.commit()

    positions_query = "Топливо дизельное летнее"
    requirements_query = "Экологический класс К5, ГОСТ 32511-2013 Требование"
    retriever = FakeRetriever(
        {
            seed.title: [_hit(analogue, chunk_id="subject", text="дизельное топливо")],
            positions_query: [
                _hit(analogue, chunk_id="position", text="топливо дизельное")
            ],
            requirements_query: [
                _hit(
                    analogue,
                    chunk_id="requirement",
                    text="Экологический класс К5, ГОСТ 32511-2013",
                )
            ],
        }
    )

    result = find_similar_procurements(
        repo,
        retriever,
        registry_number=seed.registry_number,
        limit=5,
    )

    assert result is not None
    assert result.candidate_source == "DataPlatformRagRetriever.search_all_documents"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.registry_number == analogue.registry_number
    signals = {signal.signal: signal for signal in item.signals}
    assert signals["subject"].available is True
    assert signals["subject"].score is not None and signals["subject"].score > 0
    assert signals["positions"].available is True
    assert signals["positions"].score is not None and signals["positions"].score > 0
    assert signals["customer"].score == 1.0
    assert signals["requirements"].available is True
    assert (
        signals["requirements"].score is not None and signals["requirements"].score > 0
    )
    assert {e.source_ref.rsplit(":", 1)[-1] for e in item.retrieval_evidence} == {
        "subject",
        "positions",
        "requirements",
    }
    assert item.score_calculation.startswith("Arithmetic mean")
    assert len(retriever.queries) == 3


def test_similar_procurements_rejects_semantic_hit_with_zero_subject_and_position_overlap(
    session,
):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-false",
            "registry_number": "0550000000000000011",
            "title": "Поставка дизельного топлива",
            "raw_payload": _raw(
                position="Топливо дизельное",
                requirement="Цетановое число не менее 51",
                okpd="19.20.21.300",
            ),
        }
    )
    false = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "false-analogue",
            "registry_number": "0550000000000000012",
            "title": "Техническое обслуживание серверного оборудования",
            "raw_payload": _raw(
                position="Сервер стоечного исполнения",
                requirement="Оперативная память не менее 128 ГБ",
                okpd="19.20.21.300",
            ),
        }
    )
    session.commit()

    retriever = FakeRetriever(
        {
            seed.title: [
                _hit(
                    false, chunk_id="false", text="Случайный векторный hit", score=0.99
                )
            ]
        }
    )

    result = find_similar_procurements(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.items == []
    assert result.rejected_candidates == 1


def test_similar_procurements_rejects_disjoint_okpd_major_class_even_when_titles_overlap(
    session,
):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-okpd",
            "registry_number": "0550000000000000015",
            "title": "Поставка оборудования для объекта",
            "raw_payload": _raw(
                position="Насос промышленный",
                requirement="Производительность не менее 20 м3/ч",
                okpd="28.13.14.000",
            ),
        }
    )
    false = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "false-okpd",
            "registry_number": "0550000000000000016",
            "title": "Поставка оборудования для объекта",
            "raw_payload": _raw(
                position="Сервер вычислительный",
                requirement="Оперативная память не менее 128 ГБ",
                okpd="26.20.14.000",
            ),
        }
    )
    session.commit()
    retriever = FakeRetriever(
        {
            seed.title: [
                _hit(false, chunk_id="okpd-false", text="оборудование для объекта")
            ]
        }
    )

    result = find_similar_procurements(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.items == []
    assert result.rejected_candidates == 1


def test_similar_procurements_rejects_identical_content_hash_duplicate(session):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-duplicate",
            "registry_number": "0550000000000000021",
            "title": "Поставка медицинских перчаток",
            "content_hash": "same-hash",
        }
    )
    duplicate = repo.upsert_tender(
        {
            "source": "mirror",
            "external_id": "duplicate",
            "registry_number": "0550000000000000022",
            "title": "Поставка медицинских перчаток",
            "content_hash": "same-hash",
        }
    )
    session.commit()
    retriever = FakeRetriever(
        {seed.title: [_hit(duplicate, chunk_id="dup", text="медицинские перчатки")]}
    )

    result = find_similar_procurements(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert result.items == []
    assert result.rejected_candidates == 1


def test_similar_procurements_marks_missing_structured_signals_unknown(session):
    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-minimal",
            "registry_number": "0550000000000000031",
            "title": "Поставка кабеля силового",
        }
    )
    candidate = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "candidate-minimal",
            "registry_number": "0550000000000000032",
            "title": "Кабель силовой медный",
        }
    )
    session.commit()
    retriever = FakeRetriever(
        {
            seed.title: [
                _hit(candidate, chunk_id="minimal", text="кабель силовой медный")
            ]
        }
    )

    result = find_similar_procurements(
        repo,
        retriever,
        registry_number=seed.registry_number,
    )

    assert result is not None
    assert len(result.items) == 1
    signals = {signal.signal: signal for signal in result.items[0].signals}
    assert signals["subject"].available is True
    assert signals["positions"].available is False
    assert signals["requirements"].available is False
    assert signals["customer"].available is False


def test_similar_procurements_api_route_uses_data_platform_retriever(
    client,
    session,
    monkeypatch,
):
    from src.modules.similar_procurements import router as route_module

    repo = TenderRepository(session)
    seed = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "seed-route",
            "registry_number": "0550000000000000041",
            "title": "Поставка силового кабеля",
        }
    )
    candidate = repo.upsert_tender(
        {
            "source": "eis",
            "external_id": "candidate-route",
            "registry_number": "0550000000000000042",
            "title": "Кабель силовой медный",
        }
    )
    session.commit()

    fake = FakeRetriever(
        {seed.title: [_hit(candidate, chunk_id="route", text="кабель силовой медный")]}
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
        f"/api/tender-research/similar/{seed.registry_number}",
        params={"limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["seed_registry_number"] == seed.registry_number
    assert payload["items"][0]["registry_number"] == candidate.registry_number
    assert (
        payload["candidate_source"] == "DataPlatformRagRetriever.search_all_documents"
    )
