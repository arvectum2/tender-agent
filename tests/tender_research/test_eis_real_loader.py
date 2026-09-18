from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tender_research.eis_loader import EisTenderLoader
from src.tender_research.errors import EisLoaderError
from src.tender_research.eis_real_loader import RealEisLoader
from src.tender_research.schemas import EisDocumentRaw, EisTenderRaw


class _MockAttachment:
    def __init__(self, attachment_id: str, name: str, url: str | None = None,
                 content_type: str | None = None, size_bytes: int | None = None):
        self.attachment_id = attachment_id
        self.name = name
        self.url = url
        self.content_type = content_type
        self.size_bytes = size_bytes


class TestRealEisLoader:
    def test_requires_configured_client(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        loader = RealEisLoader(soap_client=mock_client)
        assert loader.fetch_tenders() == []
        assert loader.fetch_tender_details("x") is None
        assert loader.fetch_tender_documents(EisTenderRaw(external_id="x", title="x")) == []

    def test_fetch_tenders_normalizes_search_results(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.search_procurements.return_value = [
            _make_search_result(
                procurement_id="test-001",
                notice_number="32514445109",
                registry_number="32514445109",
                title="Поставка оборудования",
                customer_name="АО Тест",
                customer_inn="7701001001",
                law="44-ФЗ",
                publication_date="2026-07-01T10:00:00",
                deadline="2026-08-01",
                initial_price=5000000.0,
                currency="RUB",
                status="Прием заявок",
            ),
        ]
        loader = RealEisLoader(soap_client=mock_client)
        tenders = loader.fetch_tenders()
        assert len(tenders) == 1
        t = tenders[0]
        assert t.external_id == "test-001"
        assert t.purchase_number == "32514445109"
        assert t.registry_number == "32514445109"
        assert t.title == "Поставка оборудования"
        assert t.customer_name == "АО Тест"
        assert t.customer_inn == "7701001001"
        assert t.law_type == "44-ФЗ"
        assert t.nmck_amount == 5000000.0
        assert t.currency == "RUB"
        assert t.status == "Прием заявок"
        assert t.eis_url == "https://zakupki.gov.ru/test"
        assert t.publication_date is not None
        assert t.application_deadline is not None
        assert t.raw_payload is not None

    def test_fetch_tenders_handles_empty_results(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.search_procurements.return_value = []
        loader = RealEisLoader(soap_client=mock_client)
        assert loader.fetch_tenders() == []

    def test_fetch_tender_details_returns_none_on_not_configured(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        loader = RealEisLoader(soap_client=mock_client)
        assert loader.fetch_tender_details("x") is None

    def test_fetch_tender_details_success(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        details = MagicMock()
        details.procurement = _make_search_result(
            procurement_id="detail-001",
            title="Детальная закупка",
            customer_name="ООО Детали",
            customer_inn="7701002002",
        )
        details.attachments = [
            _MockAttachment(
                attachment_id="att-001",
                name="spec.pdf",
                url="https://zakupki.gov.ru/spec.pdf",
                content_type="application/pdf",
                size_bytes=2048,
            ),
        ]
        mock_client.get_procurement_details.return_value = details
        loader = RealEisLoader(soap_client=mock_client)
        t = loader.fetch_tender_details("detail-001")
        assert t is not None
        assert t.external_id == "detail-001"
        assert t.title == "Детальная закупка"
        assert t.customer_name == "ООО Детали"
        assert t.documents is not None
        assert len(t.documents) == 1
        assert t.documents[0].file_name == "spec.pdf"
        assert t.documents[0].file_url == "https://zakupki.gov.ru/spec.pdf"

    def test_fetch_tender_details_handles_error(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_procurement_details.side_effect = RuntimeError("SOAP failure")
        loader = RealEisLoader(soap_client=mock_client)
        assert loader.fetch_tender_details("broken") is None

    def test_fetch_tender_documents(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.list_attachments.return_value = [
            _MockAttachment(
                attachment_id="doc-001",
                name="contract.docx",
                url="https://zakupki.gov.ru/contract.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=4096,
            ),
        ]
        tender = EisTenderRaw(external_id="test-001", title="Test")
        loader = RealEisLoader(soap_client=mock_client)
        docs = loader.fetch_tender_documents(tender)
        assert len(docs) == 1
        assert docs[0].file_name == "contract.docx"
        assert docs[0].file_url == "https://zakupki.gov.ru/contract.docx"
        assert docs[0].content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_fetch_tender_documents_not_configured(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        tender = EisTenderRaw(external_id="test-001", title="Test")
        loader = RealEisLoader(soap_client=mock_client)
        assert loader.fetch_tender_documents(tender) == []

    def test_search_parameters_passed_correctly(self):
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.search_procurements.return_value = []
        loader = RealEisLoader(soap_client=mock_client)
        date_from = datetime(2026, 7, 1)
        date_to = datetime(2026, 7, 31)
        loader.fetch_tenders(
            date_from=date_from,
            date_to=date_to,
            limit=5,
            law_type="223fz",
            query="кабель",
        )
        mock_client.search_procurements.assert_called_once()
        req = mock_client.search_procurements.call_args[0][0]
        assert req.source == "zakupki_gov_ru_soap_legacy"
        assert req.query == "кабель"
        assert req.law == "223fz"
        assert req.date_from == "2026-07-01T00:00:00"
        assert req.date_to == "2026-07-31T00:00:00"
        assert req.max_results == 5


# ── EisTenderLoader mode switching ──

class TestEisTenderLoaderMode:
    def test_demo_mode_returns_demo_data(self):
        loader = EisTenderLoader(mode="demo")
        tenders = loader.fetch_tenders()
        assert len(tenders) == 3
        assert tenders[0].external_id == "0373100000124000001"

    def test_demo_mode_fetch_details(self):
        loader = EisTenderLoader(mode="demo")
        t = loader.fetch_tender_details("0373100000124000001")
        assert t is not None
        assert t.title == "Поставка компьютерного оборудования для нужд школы № 42"

    def test_demo_mode_returns_none_for_unknown(self):
        loader = EisTenderLoader(mode="demo")
        assert loader.fetch_tender_details("nonexistent") is None

    def test_demo_mode_documents(self):
        loader = EisTenderLoader(mode="demo")
        tender = EisTenderRaw(external_id="0373100000124000001", title="Test")
        docs = loader.fetch_tender_documents(tender)
        assert len(docs) == 2

    def test_real_mode_with_mock_search(self):
        mock_real = MagicMock()
        mock_real.fetch_tenders.return_value = [
            EisTenderRaw(external_id="real-001", title="Real tender"),
        ]
        loader = EisTenderLoader(mode="real", discovery_mode="search", real_loader=mock_real)
        tenders = loader.fetch_tenders()
        assert len(tenders) == 1
        assert tenders[0].external_id == "real-001"
        mock_real.fetch_tenders.assert_called_once()

    def test_real_mode_registry_numbers_fetch_tenders_fails_closed(self):
        mock_real = MagicMock()
        loader = EisTenderLoader(mode="real", discovery_mode="registry_numbers", real_loader=mock_real)

        with pytest.raises(EisLoaderError, match="registry-number mode"):
            loader.fetch_tenders()

        mock_real.fetch_tenders.assert_not_called()

    def test_real_mode_registry_number_delegates_without_demo_fallback(self):
        mock_real = MagicMock()
        mock_real.fetch_by_registry_number.return_value = EisTenderRaw(
            external_id="real-001",
            registry_number="0848300045426000620",
            title="Real exact procurement",
        )
        loader = EisTenderLoader(mode="real", discovery_mode="registry_numbers", real_loader=mock_real)

        tender = loader.fetch_by_registry_number("0848300045426000620")

        assert tender is not None
        assert tender.external_id == "real-001"
        assert tender.registry_number == "0848300045426000620"
        mock_real.fetch_by_registry_number.assert_called_once_with("0848300045426000620")

    def test_real_mode_delegates_details(self):
        mock_real = MagicMock()
        mock_real.fetch_tender_details.return_value = EisTenderRaw(
            external_id="real-001", title="Real details",
        )
        loader = EisTenderLoader(mode="real", real_loader=mock_real)
        t = loader.fetch_tender_details("real-001")
        assert t is not None
        assert t.title == "Real details"

    def test_real_mode_delegates_documents(self):
        mock_real = MagicMock()
        mock_real.fetch_tender_documents.return_value = [
            EisDocumentRaw(file_name="doc.pdf", file_url="https://example.com/doc.pdf"),
        ]
        loader = EisTenderLoader(mode="real", real_loader=mock_real)
        docs = loader.fetch_tender_documents(EisTenderRaw(external_id="x", title="x"))
        assert len(docs) == 1
        assert docs[0].file_name == "doc.pdf"


# ── Error classification ──

class TestEisErrorClassification:
    def test_connection_reset_not_missing_token(self):
        from src.tender_research.errors import classify_eis_error, EisConnectionResetError, EisMissingTokenError
        err = classify_eis_error(RuntimeError("[Errno 54] Connection reset by peer"))
        assert isinstance(err, EisConnectionResetError)
        assert not isinstance(err, EisMissingTokenError)

    def test_missing_token_classified(self):
        from src.tender_research.errors import classify_eis_error, EisMissingTokenError
        err = classify_eis_error(RuntimeError("token not configured"))
        assert isinstance(err, EisMissingTokenError)

    def test_auth_failed_classified(self):
        from src.tender_research.errors import classify_eis_error, EisAuthFailedError
        err = classify_eis_error(RuntimeError("HTTP 403 Forbidden"))
        assert isinstance(err, EisAuthFailedError)


# ── Check config diagnostics ──

class TestRealEisLoaderCheckConfig:
    def test_check_config_unconfigured(self):
        from unittest.mock import MagicMock
        from src.tender_research.eis_real_loader import RealEisLoader
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        loader = RealEisLoader(soap_client=mock_client)
        info = loader.check_config()
        assert info["configured"] is False
        assert info["token_present"] is False
        assert "token_masked" in info
        assert info["available_methods"] == ["(none confirmed)"]

    def test_check_config_masks_token(self):
        from unittest.mock import MagicMock, patch
        import os
        with patch("src.tender_research.eis_real_loader.get_zakupki_soap_settings") as mock_settings:
            settings = MagicMock()
            settings.token = "abcdefghijklmnop"
            settings.configured = True
            settings.token_owner = "individual"
            settings.individual_base_url = "https://int.zakupki.gov.ru/"
            settings.base_url = "https://int44.zakupki.gov.ru/"
            mock_settings.return_value = settings
            mock_client = MagicMock()
            mock_client.is_configured.return_value = True
            loader = RealEisLoader(soap_client=mock_client)
            info = loader.check_config()
            assert info["token_masked"] == "abcd****mnop"


# ── Fetch by registry number ──

class TestRealEisLoaderFetchByRegistry:
    def test_fetch_by_registry_no_data(self):
        from unittest.mock import MagicMock
        from src.tender_research.errors import EisNoDataError
        from src.modules.tender_operator_agent_demo.procurement_schemas import DocsArchiveResult
        mock_client = MagicMock()
        mock_client.is_configured.return_value = True
        mock_client.get_docs_by_reestr_number.return_value = DocsArchiveResult(
            request_id="test", status="no_data", warnings=["no data"],
        )
        loader = RealEisLoader(soap_client=mock_client)
        import pytest
        with pytest.raises(EisNoDataError):
            loader.fetch_by_registry_number("0000000000000000")

    def test_fetch_by_registry_not_configured(self):
        from unittest.mock import MagicMock
        from src.tender_research.errors import EisMissingTokenError
        mock_client = MagicMock()
        mock_client.is_configured.return_value = False
        loader = RealEisLoader(soap_client=mock_client)
        import pytest
        with pytest.raises(EisMissingTokenError):
            loader.fetch_by_registry_number("0000000000000000")


# ── Registry numbers loader ──

class TestRegistryNumbersLoader:
    def test_reads_file(self):
        path = Path("data/eis_seed/registry_numbers.txt")
        if not path.exists():
            path = Path("/Users/master/Documents/AI-Corporation/data/eis_seed/registry_numbers.txt")
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        assert len(lines) >= 1
        assert lines[0].isdigit()

    def test_dedupes_numbers(self):
        numbers = ["0373100000124000001", "0373100000124000001", "0373100000124000002"]
        seen = set()
        deduped = [n for n in numbers if not (n in seen or seen.add(n))]
        assert len(deduped) == 2

    def test_fetch_by_registry_number_demo_mode(self):
        loader = EisTenderLoader(mode="demo")
        t = loader.fetch_by_registry_number("0373100000124000001")
        assert t is not None
        assert t.external_id == "0373100000124000001"

    def test_fetch_by_registry_number_demo_unknown(self):
        loader = EisTenderLoader(mode="demo")
        t = loader.fetch_by_registry_number("0000000000000000")
        assert t is None


# ── Helper ──

def _make_search_result(**overrides) -> MagicMock:
    r = MagicMock()
    r.procurement_id = overrides.get("procurement_id", "test-id")
    r.notice_number = overrides.get("notice_number")
    r.registry_number = overrides.get("registry_number")
    r.title = overrides.get("title", "Test procurement")
    r.customer_name = overrides.get("customer_name", "Test customer")
    r.customer_inn = overrides.get("customer_inn")
    r.law = overrides.get("law")
    r.source = "zakupki_gov_ru_soap_legacy"
    r.source_url = overrides.get("source_url", "https://zakupki.gov.ru/test")
    r.publication_date = overrides.get("publication_date")
    r.deadline = overrides.get("deadline")
    r.initial_price = overrides.get("initial_price")
    r.currency = overrides.get("currency")
    r.status = overrides.get("status")
    r.attachments_count = 0
    r.attachments_status = "manual_upload_required"
    r.can_download_attachments = False
    r.requires_manual_upload = True
    r.warnings = []

    def model_dump(*a, **kw):
        return {
            "procurement_id": r.procurement_id,
            "title": r.title,
            "customer_name": r.customer_name,
        }

    r.model_dump = model_dump
    return r
