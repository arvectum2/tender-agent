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
