"""Sanitized source-layout fixtures; no customer documents or EIS credentials."""
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from src.tender_research.eis_real_loader import RealEisLoader
from src.tender_research.providers.ri223_soap_evidence import (
    Ri223EvidenceError,
    parse_ri223_archive,
)

NUMBER = "32616447910"
NS = "http://zakupki.gov.ru/223fz/purchase/1"


def _notice(number: str = NUMBER, *, lots: str | None = None) -> str:
    if lots is None:
        lots = """
        <lot><ordinalNumber>1</ordinalNumber><lotData>
          <subject>Тестовые услуги</subject><initialSum>280800</initialSum>
          <currency><code>RUB</code></currency><lotItems>
            <lotItem><ordinalNumber>1</ordinalNumber>
              <okpd2><code>62.02.20.120</code><name>Тестовое обследование</name></okpd2>
              <okei><code>876</code><name>Условная единица</name></okei><qty>1</qty>
            </lotItem>
          </lotItems></lotData></lot>
        """
    return f"""<purchaseNotice xmlns="{NS}"><header/><body><item><purchaseNoticeData>
        <registrationNumber>{number}</registrationNumber>
        <name>Тестовая закупка по 223-ФЗ</name>
        <publicationDateTime>2026-10-08T12:13:44</publicationDateTime>
        <version>1</version><status>P</status>
        <attachments><document><contentUid>test-uid</contentUid><fileName>public.pdf</fileName>
        <url>https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=test-uid</url>
        </document></attachments>
        <lots>{lots}</lots>
        </purchaseNoticeData></item></body></purchaseNotice>"""


def _protocol(notice_number: str = NUMBER) -> str:
    return f"""<purchaseProtocol xmlns="{NS}"><header/><body><item><purchaseProtocolData>
        <purchaseInfo><purchaseNoticeNumber>{notice_number}</purchaseNoticeNumber></purchaseInfo>
        <registrationNumber>{notice_number}-01</registrationNumber>
        <typeName>Протокол тестовый</typeName>
        <status>P</status><version>1</version>
        </purchaseProtocolData></item></body></purchaseProtocol>"""


def _archive(tmp_path: Path, docs: dict[str, str]) -> Path:
    archive = tmp_path / "ri223.zip"
    with ZipFile(archive, "w") as bundle:
        for name, content in docs.items():
            bundle.writestr(name, content)
    return archive


def test_exact_notice_lot_position_and_protocol_with_source_hashes(tmp_path):
    archive = _archive(tmp_path, {"notice.xml": _notice(), "protocol.xml": _protocol()})
    tender = parse_ri223_archive(archive, NUMBER)
    assert tender.law_type == "223fz"
    assert tender.registry_number == NUMBER
    assert tender.nmck_amount == 280800.0
    assert tender.currency == "RUB"
    assert tender.status is None  # SOAP transport completed != procurement complete
    assert tender.raw_payload["procurement_status"] == "UNKNOWN"
    assert tender.raw_payload["amendment_semantics"] == "UNKNOWN"
    assert tender.raw_payload["clarifications"] == "NOT_OBSERVED"
    lot = tender.raw_payload["lots"][0]
    assert lot["subject"] == "Тестовые услуги"
    position = lot["positions"][0]
    assert position["okpd2_code"] == "62.02.20.120"
    assert position["quantity"] == "1"
    assert position["unit_code"] == "876"
    assert tender.raw_payload["protocols"][0]["notice_number"] == NUMBER
    assert tender.raw_payload["protocols_observed"] is True
    assert len(tender.documents) == 1
    assert tender.documents[0].source_document_id == "test-uid"
    assert tender.documents[0].raw_meta["evidence"]["xml_member"] == "notice.xml"
    assert position["evidence"]["xml_member"] == "notice.xml"
    assert "/lotItem[1]" in position["evidence"]["xpath"]
    assert len(position["evidence"]["xml_sha256"]) == 64
    assert len(position["evidence"]["archive_sha256"]) == 64


def test_missing_protocol_is_not_fabricated(tmp_path):
    evidence = parse_ri223_archive(_archive(tmp_path, {"notice.xml": _notice()}), NUMBER)
    assert evidence.raw_payload["protocols"] == []
    assert evidence.raw_payload["protocols_observed"] is False


def test_multiple_lots_positions_are_separately_source_bound_and_price_unknown(tmp_path):
    lots = """
    <lot><ordinalNumber>1</ordinalNumber><lotData><subject>Услуга 1</subject><initialSum>100</initialSum>
    <lotItems><lotItem><ordinalNumber>1</ordinalNumber><qty>5</qty></lotItem>
    <lotItem><ordinalNumber>2</ordinalNumber><qty>10</qty></lotItem></lotItems></lotData></lot>
    <lot><ordinalNumber>2</ordinalNumber><lotData><subject>Услуга 2</subject><initialSum>200</initialSum>
    <lotItems><lotItem><ordinalNumber>1</ordinalNumber><qty>2</qty></lotItem></lotItems></lotData></lot>"""
    tender = parse_ri223_archive(_archive(tmp_path, {"notice.xml": _notice(lots=lots)}), NUMBER)
    assert len(tender.raw_payload["lots"]) == 2
    assert [len(x["positions"]) for x in tender.raw_payload["lots"]] == [2, 1]
    assert tender.nmck_amount is None  # do not conflate lot values with notice NMCK


@pytest.mark.parametrize("docs, number, message", [
    ({"notice.xml": _notice("32616440000")}, NUMBER, "number does not match"),
    ({"notice.xml": _notice(), "protocol.xml": _protocol("32616449999")}, NUMBER, "not bound"),
    ({"a.xml": _notice(), "b.xml": _notice()}, NUMBER, "one notice version"),
    ({"notice.xml": "<unrelated />"}, NUMBER, "unsupported"),
    ({"notice.xml": _notice(lots="")}, NUMBER, "no supported source-bound lots"),
    ({"notice.xml": "<!DOCTYPE lol [<!ENTITY x 'bomb'>]>" + _notice()}, NUMBER, "DTD"),
])
def test_invalid_or_ambiguous_corpus_fails_closed(tmp_path, docs, number, message):
    with pytest.raises(Ri223EvidenceError, match=message):
        parse_ri223_archive(_archive(tmp_path, docs), number)


def test_oversize_member_fails_before_xml_parse(tmp_path):
    from src.tender_research.providers.ri223_soap_evidence import MAX_XML_BYTES
    archive = _archive(tmp_path, {"notice.xml": _notice() + " " * (MAX_XML_BYTES + 1)})
    with pytest.raises(Ri223EvidenceError, match="too large"):
        parse_ri223_archive(archive, NUMBER)


def test_real_loader_ri223_explicit_opt_in_and_temp_cleanup(tmp_path):
    source = _archive(tmp_path, {"notice.xml": _notice(), "protocol.xml": _protocol()})
    seen = []
    class Client:
        def is_configured(self): return True
        def get_docs_by_reestr_number(self, number, *, subsystem_type):
            seen.append(("soap", number, subsystem_type))
            return SimpleNamespace(status="completed", archive_url="https://zakupki.gov.ru/doc.zip", archive_urls=[])
        def download_archive(self, url, target):
            seen.append(("download", url))
            (target / "documentation-archive.zip").write_bytes(source.read_bytes())
            return SimpleNamespace(stored_name="documentation-archive.zip")
    tender = RealEisLoader(soap_client=Client()).fetch_by_registry_number(NUMBER, law_type="223fz")
    assert tender.law_type == "223fz"
    assert len(tender.raw_payload["protocols"]) == 1
    assert seen == [("soap", NUMBER, "RI223"), ("download", "https://zakupki.gov.ru/doc.zip")]


def test_real_loader_rejects_ambiguous_download_without_fetching():
    from src.tender_research.errors import EisLoaderError
    class Client:
        def is_configured(self): return True
        def get_docs_by_reestr_number(self, number, *, subsystem_type):
            return SimpleNamespace(status="completed", archive_url="https://zakupki.gov.ru/a.zip", archive_urls=["https://zakupki.gov.ru/b.zip"])
        def download_archive(self, *args):
            raise AssertionError("must not download conflicting archive choices")
    with pytest.raises(EisLoaderError, match="ambiguous"):
        RealEisLoader(soap_client=Client()).fetch_by_registry_number(NUMBER, law_type="223fz")


def test_document_host_rejects_untrusted_xml_link(tmp_path):
    from src.tender_research.providers.ri223_soap_evidence import Ri223EvidenceError
    evil = _notice().replace(
        "https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=test-uid",
        "https://zakupki.gov.ru.evil.example/doc",
    )
    with pytest.raises(Ri223EvidenceError, match="URL origin"):
        parse_ri223_archive(_archive(tmp_path, {"notice.xml": evil}), NUMBER)


def test_duplicate_zip_xml_member_fails_closed(tmp_path):
    archive = tmp_path / "repeated.zip"
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(archive, "w") as bundle:
            bundle.writestr("notice.xml", _notice())
            bundle.writestr("notice.xml", _notice())
    with pytest.raises(Ri223EvidenceError, match="duplicate ZIP"):
        parse_ri223_archive(archive, NUMBER)


def test_ri223_end_to_end_opt_in_pipeline_persists_source_metadata(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.shared.db.base import Base
    from src.tender_research.config import TenderResearchConfig
    from src.tender_research.eis_loader import EisTenderLoader
    from src.tender_research.pipeline import TenderResearchPipeline
    from src.tender_research.repository import TenderRepository

    source = _archive(tmp_path, {"notice.xml": _notice(), "protocol.xml": _protocol()})

    class Client:
        def is_configured(self): return True
        def get_docs_by_reestr_number(self, number, *, subsystem_type):
            assert number == NUMBER and subsystem_type == "RI223"
            return SimpleNamespace(status="completed", archive_url="https://zakupki.gov.ru/archive.zip", archive_urls=[])
        def download_archive(self, url, target):
            assert url == "https://zakupki.gov.ru/archive.zip"
            (target / "documentation-archive.zip").write_bytes(source.read_bytes())
            return SimpleNamespace(stored_name="documentation-archive.zip")

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    loader = EisTenderLoader(mode="real", real_loader=RealEisLoader(soap_client=Client()))
    pipeline = TenderResearchPipeline(
        session, config=TenderResearchConfig(data_dir=str(tmp_path / "data")),
        eis_loader=loader,
    )
    for _ in range(2):
        result = pipeline.ingest_eis_by_registry_numbers([NUMBER], law_type="223fz")
        assert result["saved"] == 1 and result["errors"] == []
    repo = TenderRepository(session)
    tender = repo.get_tender_by_external("eis", NUMBER)
    assert tender.law_type == "223fz"
    assert tender.raw_payload["lots"][0]["positions"][0]["okpd2_code"] == "62.02.20.120"
    assert tender.raw_payload["protocols"][0]["notice_number"] == NUMBER
    assert repo.count_tenders() == 1
    assert repo.count_documents() == 1
