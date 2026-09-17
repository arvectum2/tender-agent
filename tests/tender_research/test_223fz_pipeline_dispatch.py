from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.db.base import Base
from src.tender_research.config import TenderResearchConfig
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.providers.public_44fz_search import (
    PublicDocumentLink,
    PublicSearchStatus,
    PublicTenderDetail,
    PublicTenderSearchItem,
    PublicTenderSearchPage,
)
from src.tender_research.registry_discovery import (
    DiscoveredRegistryNumber,
    RegistryNumberDiscovery,
    SourceType,
)
from src.tender_research.repository import TenderRepository


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_223fz_discovery_uses_separate_provider(monkeypatch):
    discovery = RegistryNumberDiscovery(config=TenderResearchConfig())
    item = PublicTenderSearchItem(
        registry_number="22300000000000000001",
        law_type="223fz",
        title="223 test",
        card_url="https://zakupki.gov.ru/223/card/1",
        source_url="https://zakupki.gov.ru/223/search",
    )
    page = PublicTenderSearchPage(
        items=[item], page=1, page_size=10,
        status=PublicSearchStatus.SUCCESS, source_url=item.source_url,
    )
    monkeypatch.setattr(
        discovery._public_223fz_provider, "search_pages", lambda **_: [page]
    )
    monkeypatch.setattr(
        discovery._public_provider,
        "search_pages",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("44-FZ provider must not be used")
        ),
    )

    result = discovery.discover(
        source="external_public_223fz", days_back=1, limit=10, page_size=10
    )

    assert result.selected_source_type == SourceType.EXTERNAL_PUBLIC_223FZ
    assert result.numbers[0].law_type == "223fz"
    assert result.numbers[0].source_type == SourceType.EXTERNAL_PUBLIC_223FZ


def test_223fz_pipeline_dispatch_and_repeated_ingest_are_idempotent(
    tmp_path, monkeypatch
):
    session = _session()
    pipeline = TenderResearchPipeline(
        session, config=TenderResearchConfig(data_dir=str(tmp_path))
    )
    discovered = DiscoveredRegistryNumber(
        registry_number="22300000000000000001",
        source="external_public_223fz",
        source_type=SourceType.EXTERNAL_PUBLIC_223FZ,
        tender_title="223 test",
        customer_name="АО Заказчик",
        law_type="223fz",
        card_url="https://zakupki.gov.ru/223/card/1",
        source_url="https://zakupki.gov.ru/223/search",
    )
    detail = PublicTenderDetail(
        registry_number=discovered.registry_number,
        title="223 test",
        customer_name="АО Заказчик",
        law_type="223fz",
        card_url=discovered.card_url,
        source_url=discovered.card_url,
        network_status=PublicSearchStatus.SUCCESS,
        document_links=[
            PublicDocumentLink(
                title="ТЗ", file_name="tz.pdf",
                url="https://zakupki.gov.ru/223/file/1",
            )
        ],
        raw={"source_regime": "223fz"},
    )
    monkeypatch.setattr(
        pipeline._public_223fz_provider, "fetch_detail", lambda *a, **k: detail
    )
    monkeypatch.setattr(
        pipeline._public_provider,
        "fetch_detail",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("44-FZ detail provider must not be used")
        ),
    )
    monkeypatch.setattr(
        pipeline, "_fetch_eis_by_registry_number_safe",
        lambda *_: (None, "unavailable"),
    )

    tender1, _ = pipeline._ingest_discovered_tender(discovered)
    session.commit()
    tender2, _ = pipeline._ingest_discovered_tender(discovered)
    session.commit()

    repo = TenderRepository(session)
    assert tender1.id == tender2.id
    assert repo.count_tenders() == 1
    assert repo.count_documents() == 1
    assert tender2.law_type == "223fz"
    rows = pipeline._public_documents_to_rows(detail)
    assert rows[0]["raw_meta"]["source"] == "external_public_223fz_detail"
