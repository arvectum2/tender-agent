from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shared.db.base import Base
from src.tender_research.config import TenderResearchConfig
from src.tender_research.errors import EisNoDataError
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.providers.public_44fz_search import (
    PublicDocumentLink,
    PublicSearchStatus,
    PublicTenderDetail,
)
from src.tender_research.registry_discovery import (
    DiscoveredRegistryNumber,
    DiscoveryResult,
    SourceType,
)
from src.tender_research.repository import TenderRepository
from src.tender_research.schemas import EisTenderRaw


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class FakeEisLoader:
    def __init__(self, raw_by_number=None):
        self.raw_by_number = raw_by_number or {}

    def fetch_by_registry_number(self, registry_number: str):
        value = self.raw_by_number.get(registry_number)
        if isinstance(value, Exception):
            raise value
        return value

    def fetch_tender_documents(self, tender):
        return []


class FakePublicProvider:
    def __init__(self, details: dict[str, PublicTenderDetail]):
        self._details = details

    def fetch_detail(self, item_or_url=None, registry_number=None, card_url=None):
        key = registry_number or card_url
        return self._details[key]


def _pipeline(raw_by_number=None, details=None) -> TenderResearchPipeline:
    session = _session()
    config = TenderResearchConfig(
        enabled=True,
        data_dir="/tmp/tender_research_discovery_ingest",
        web_search_enabled=False,
        web_fetch_enabled=False,
    )
    pipeline = TenderResearchPipeline(
        session,
        config=config,
        eis_loader=FakeEisLoader(raw_by_number=raw_by_number),
    )
    pipeline._public_provider = FakePublicProvider(details or {})
    pipeline.run_full = lambda tender_id: {"tender_id": tender_id, "documents_downloaded": 0, "documents_failed": 0}
    return pipeline


def test_ingest_preserves_discovery_metadata_when_soap_has_no_data():
    registry_number = "0373200000000000001"
    pipeline = _pipeline(
        raw_by_number={registry_number: EisNoDataError("no data")},
        details={
            registry_number: PublicTenderDetail(
                registry_number=registry_number,
                title=None,
                customer_name=None,
                network_status=PublicSearchStatus.TIMEOUT,
                error_message="timed out",
            )
        },
    )
    pipeline.discover_registry_numbers = lambda **kwargs: DiscoveryResult(
        numbers=[
            DiscoveredRegistryNumber(
                registry_number=registry_number,
                source="external_public_44fz",
                source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
                tender_title="Реальный title из search",
                customer_name="ГБУ Заказчик",
                publication_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
                nmck_amount=500000.0,
                source_url="https://zakupki.gov.ru/search",
                card_url="https://zakupki.gov.ru/card",
            )
        ],
        selected_source="external_public_44fz",
        selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
        discovered_count=1,
    )

    pipeline.run_discovered_batch(source="external_public_44fz", limit=1)

    repo = TenderRepository(pipeline._session)
    tender = repo.get_tender_by_external("eis", registry_number)
    assert tender is not None
    assert tender.title == "Реальный title из search"
    assert tender.customer_name == "ГБУ Заказчик"
    assert tender.publication_date.date().isoformat() == "2026-07-01"
    assert tender.nmck_amount == 500000.0
    assert tender.eis_url == "https://zakupki.gov.ru/card"
    assert repo.count_customers() == 1


def test_soap_real_field_overrides_discovery_but_placeholder_does_not():
    registry_number = "0373200000000000002"
    soap_raw = EisTenderRaw(
        external_id=registry_number,
        registry_number=registry_number,
        title="Закупка 0373200000000000002",
        customer_name="",
        publication_date=None,
        nmck_amount=None,
        raw_payload={"soap": "ok"},
    )
    pipeline = _pipeline(
        raw_by_number={registry_number: soap_raw},
        details={
            registry_number: PublicTenderDetail(
                registry_number=registry_number,
                title="Title from detail",
                customer_name="Заказчик из detail",
                network_status=PublicSearchStatus.SUCCESS,
            )
        },
    )
    pipeline.discover_registry_numbers = lambda **kwargs: DiscoveryResult(
        numbers=[
            DiscoveredRegistryNumber(
                registry_number=registry_number,
                source="external_public_44fz",
                source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
                tender_title="Title from search",
                customer_name="Заказчик из search",
            )
        ],
        selected_source="external_public_44fz",
        selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
        discovered_count=1,
    )

    pipeline.run_discovered_batch(source="external_public_44fz", limit=1)

    tender = TenderRepository(pipeline._session).get_tender_by_external("eis", registry_number)
    assert tender.title == "Title from detail"
    assert tender.customer_name == "Заказчик из detail"


def test_placeholder_title_is_used_only_as_last_resort():
    registry_number = "0373200000000000003"
    pipeline = _pipeline(
        raw_by_number={registry_number: EisNoDataError("no data")},
        details={
            registry_number: PublicTenderDetail(
                registry_number=registry_number,
                title=None,
                customer_name=None,
                network_status=PublicSearchStatus.SUCCESS,
            )
        },
    )
    pipeline.discover_registry_numbers = lambda **kwargs: DiscoveryResult(
        numbers=[DiscoveredRegistryNumber(registry_number=registry_number, source="external_public_44fz")],
        selected_source="external_public_44fz",
        selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
        discovered_count=1,
    )

    pipeline.run_discovered_batch(source="external_public_44fz", limit=1)

    tender = TenderRepository(pipeline._session).get_tender_by_external("eis", registry_number)
    assert tender.title == f"Закупка {registry_number}"


def test_public_document_links_are_idempotent_fallback():
    registry_number = "0373200000000000004"
    detail = PublicTenderDetail(
        registry_number=registry_number,
        title="Title",
        customer_name="Customer",
        network_status=PublicSearchStatus.SUCCESS,
        document_links=[
            PublicDocumentLink(
                title="Документ",
                file_name="spec.pdf",
                url="https://zakupki.gov.ru/file.pdf?utm_source=one&doc=1",
                content_type="application/pdf",
                raw={"uid": "UID-1"},
            )
        ],
    )
    pipeline = _pipeline(
        raw_by_number={registry_number: EisNoDataError("no data")},
        details={registry_number: detail},
    )
    pipeline.discover_registry_numbers = lambda **kwargs: DiscoveryResult(
        numbers=[DiscoveredRegistryNumber(registry_number=registry_number, source="external_public_44fz")],
        selected_source="external_public_44fz",
        selected_source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
        discovered_count=1,
    )

    pipeline.run_discovered_batch(source="external_public_44fz", limit=1)
    pipeline.run_discovered_batch(source="external_public_44fz", limit=1)

    repo = TenderRepository(pipeline._session)
    tender = repo.get_tender_by_external("eis", registry_number)
    assert tender is not None
    assert repo.count_documents() == 1
    document = tender.documents[0]
    assert document.file_name == "spec.pdf"
    assert document.raw_meta["source"] == "external_public_44fz_detail"


def test_public_registry_ingestion_seam_persists_public_detail_and_documents():
    registry_number = "0373200000000000005"
    detail = PublicTenderDetail(
        registry_number=registry_number,
        title="Разработка информационной системы",
        customer_name="ГБУ Тест",
        network_status=PublicSearchStatus.SUCCESS,
        document_links=[
            PublicDocumentLink(
                title="Техническое задание",
                file_name="tz.pdf",
                url="https://zakupki.gov.ru/tz.pdf?doc=5",
                content_type="application/pdf",
                raw={"uid": "UID-5"},
            )
        ],
    )
    pipeline = _pipeline(
        raw_by_number={registry_number: EisNoDataError("no data")},
        details={registry_number: detail},
    )
    pipeline._lookup_public_discovered_item = lambda number, existing=None: DiscoveredRegistryNumber(
        registry_number=number,
        source="external_public_44fz",
        source_type=SourceType.EXTERNAL_PUBLIC_44FZ,
        tender_title="Разработка информационной системы",
        customer_name="ГБУ Тест",
        card_url="https://zakupki.gov.ru/card-5",
        source_url="https://zakupki.gov.ru/card-5",
    )

    tender, summary = pipeline.ingest_public_by_registry_number(registry_number)

    assert tender.registry_number == registry_number
    assert tender.title == "Разработка информационной системы"
    assert tender.customer_name == "ГБУ Тест"
    assert summary["public_document_links_found"] == 1
    assert TenderRepository(pipeline._session).count_documents() == 1
