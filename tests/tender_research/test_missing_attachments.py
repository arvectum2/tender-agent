from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.db import models  # noqa: F401
from src.shared.db.base import Base
from src.tender_research.providers.public_44fz_search import (
    PublicDocumentLink,
    PublicNoticeRevision,
    PublicTenderDetail,
)
from src.tender_research.rag.missing_attachments import recover_missing_attachments
from src.tender_research.repository import TenderRepository

NUMBER = "0173100007526000046"
CARD = f"https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber={NUMBER}"


@pytest.fixture
def scenario():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = TenderRepository(session)
        tender = repo.upsert_tender(
            {
                "source": "eis",
                "external_id": NUMBER,
                "registry_number": NUMBER,
                "law_type": "44fz",
                "title": "Test",
                "raw_payload": {
                    "public_detail": {
                        "card_url": CARD,
                        "network_status": "network_error",
                    }
                },
            }
        )
        session.commit()
        link = PublicDocumentLink(
            file_name="spec.docx",
            url="https://zakupki.gov.ru/filestore/public/1",
            raw={"uid": "one"},
        )
        rev = PublicNoticeRevision(
            revision=1,
            active=True,
            publication_timestamp="19.11.2026",
            source_url=f"https://zakupki.gov.ru/epz/order/notice/printForm/viewByVersionNumber.html?regNumber={NUMBER}&versionNumber=1",
            document_links=[link],
        )
        detail = PublicTenderDetail(
            registry_number=NUMBER,
            law_type="44fz",
            document_links=[link],
            active_revision=rev,
            documents_html="<html>fixture</html>",
            raw={
                "documents_fetch_status": "success",
                "document_revision_selection": {
                    "status": "active_revision_selected",
                    "requires_review": False,
                },
            },
        )
        provider = Mock()
        provider.fetch_detail.return_value = detail
        yield repo, tender, detail, provider


def test_missing_inventory_recovered_idempotently(scenario):
    repo, tender, _, provider = scenario
    old = tender.raw_payload
    assert recover_missing_attachments(repo, tender, provider=provider) == 1
    repo._session.commit()
    assert len(tender.documents) == 1
    assert tender.documents[0].raw_meta["revision"] == 1
    assert tender.raw_payload == old
    assert recover_missing_attachments(repo, tender, provider=provider) == 0
    provider.fetch_detail.assert_called_once()


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_registry",
        "ambiguous",
        "missing_revision",
        "foreign_link",
        "network_error",
    ],
)
def test_invalid_evidence_is_not_persisted(scenario, defect):
    repo, tender, detail, provider = scenario
    if defect == "wrong_registry":
        detail.registry_number = "0" * 19
    elif defect == "ambiguous":
        detail.raw["document_revision_selection"]["requires_review"] = True
    elif defect == "missing_revision":
        detail.active_revision = None
    elif defect == "foreign_link":
        detail.document_links[0].url = "https://example.invalid/test"
    else:
        detail.network_status = "network_error"
    with pytest.raises(ValueError):
        recover_missing_attachments(repo, tender, provider=provider)
    assert tender.documents == []


def test_ordinary_reimport_keeps_recovered_inventory_and_status(scenario):
    from src.tender_research.rag.missing_attachments import preserve_recovered_inventory

    repo, tender, detail, provider = scenario
    assert recover_missing_attachments(repo, tender, provider=provider) == 1
    doc = tender.documents[0]
    doc.download_status = "downloaded"
    doc.text_extraction_status = "extracted"
    repo._session.commit()
    assert preserve_recovered_inventory(tender, detail)
    assert len(tender.documents) == 1
    assert doc.download_status == "downloaded"
    assert doc.text_extraction_status == "extracted"


@pytest.mark.parametrize(
    "defect", ["new_revision", "missing_link", "changed_link", "soap", "network"]
)
def test_recovered_inventory_reimport_fails_closed(scenario, defect):
    from src.tender_research.errors import DocumentIdentityConflictError
    from src.tender_research.rag.missing_attachments import preserve_recovered_inventory

    repo, tender, detail, provider = scenario
    assert recover_missing_attachments(repo, tender, provider=provider) == 1
    repo._session.commit()
    if defect == "new_revision":
        detail.active_revision.revision = 2
    elif defect == "missing_link":
        detail.document_links.clear()
    elif defect == "changed_link":
        detail.document_links[0].url += "2"
    elif defect == "network":
        detail.network_status = "network_error"
    with pytest.raises(DocumentIdentityConflictError):
        preserve_recovered_inventory(tender, detail, soap_documents=defect == "soap")
    assert len(tender.documents) == 1


def test_ordinary_empty_card_unaffected(scenario):
    from src.tender_research.rag.missing_attachments import preserve_recovered_inventory

    _, tender, detail, _ = scenario
    assert not preserve_recovered_inventory(tender, detail)


def test_pipeline_reimport_does_not_duplicate_or_reset(scenario):
    from src.tender_research.pipeline import TenderResearchPipeline
    from src.tender_research.registry_discovery import DiscoveredRegistryNumber

    repo, tender, detail, provider = scenario
    assert recover_missing_attachments(repo, tender, provider=provider) == 1
    doc = tender.documents[0]
    original_id = doc.id
    doc.download_status = "downloaded"
    doc.text_extraction_status = "extracted"
    repo._session.commit()
    pipeline = TenderResearchPipeline.__new__(TenderResearchPipeline)
    discovered = DiscoveredRegistryNumber(registry_number=NUMBER, card_url=CARD)
    result = pipeline._build_upsert_from_discovery(
        discovered, detail, None, "test", existing_tender=tender
    )
    assert result.documents == []
    for row in result.documents:
        repo.upsert_document({**row, "tender_id": tender.id})
    repo._session.flush()
    repo._session.expire(tender, ["documents"])
    assert len(tender.documents) == 1
    assert tender.documents[0].id == original_id
    assert tender.documents[0].download_status == "downloaded"
    assert tender.documents[0].text_extraction_status == "extracted"
