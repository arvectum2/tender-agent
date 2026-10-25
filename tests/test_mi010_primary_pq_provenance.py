from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_attachment_manifest import (
    _public_filestore_digest,
    attachment_manifest,
)
from src.modules.market_intelligence.eis_source_ledger import (
    extract_archive,
    link_original_documents,
)


def _zip(tmp_path: Path, members: dict[str, bytes]) -> tuple[Path, str]:
    path = tmp_path / "official.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path: Path, sha: str):
    return extract_archive(path, official_archive_sha256=sha, subsystem="RI223",
                           region="77", exact_date="2026-10-25")


def _notice(kind: str, *, subject: str = "СТАТКОМ", price: str = "6795960",
            inn: str = "4716016979") -> bytes:
    return f"""<{kind}><body><item><{kind}Data>
<registrationNumber>32313008364</registrationNumber>
<customer><mainInfo><fullName>Тестовая сетевая компания</fullName><inn>{inn}</inn></mainInfo></customer>
<lots><lot><ordinalNumber>1</ordinalNumber><lotData>
<subject>{subject}</subject><currency><code>RUB</code></currency>
<initialSum>{price}</initialSum></lotData></lot></lots>
</{kind}Data></item></body></{kind}>""".encode()


def _protocol(kind: str) -> bytes:
    return f"""<{kind}><body><item><{kind}Data>
<purchaseInfo><purchaseNoticeNumber>32313008364</purchaseNoticeNumber></purchaseInfo>
<registrationNumber>PROTO-44</registrationNumber>
<lotApplicationsList><protocolLotApplications>
<lot><ordinalNumber>1</ordinalNumber></lot>
<application><applicationNumber>2</applicationNumber>
<provider><mainInfo><inn>1234567890</inn></mainInfo></provider>
<price>5200000</price><accepted>true</accepted><contractSigned>true</contractSigned>
</application></protocolLotApplications></lotApplicationsList>
</{kind}Data></item></body></{kind}>""".encode()


@pytest.mark.parametrize(("notice_kind", "protocol_kind"), [
    ("purchaseNoticeZKESMBO", "purchaseProtocolSummingupZKESMBO"),
    ("purchaseNoticeZPESMBO", "purchaseProtocolRZ1ZPESMBO"),
])
def test_actual_223_source_types_link_with_no_fake_award(tmp_path, notice_kind, protocol_kind):
    path, sha = _zip(tmp_path, {
        "notice-v1.xml": _notice(notice_kind),
        "notice-v2.xml": _notice(notice_kind, subject="Реконструкция ПС + СТАТКОМ"),
        "protocol.xml": _protocol(protocol_kind),
    })
    rows = _source(path, sha)
    assert len(rows) == 3
    notices = [row for row in rows if row["record_kind"] == "notice"]
    assert len(notices) == 2
    assert all(x["customer_inn_evidence"] == "4716016979" for x in notices)
    assert all(x["customer_company_name"] == "Тестовая сетевая компания" for x in notices)
    assert all(x["initial_lots"][0]["initial_sum_text"] == "6795960" for x in notices)
    assert all(x["initial_lots"][0]["currency_code"] == "RUB" for x in notices)
    assert all(x["initial_lots"][0]["price_kind"] == "source_initial_lot_sum_not_contract" for x in notices)
    protocol = next(row for row in rows if row["record_kind"] == "protocol")
    assert protocol["notice_number"] == "32313008364"
    assert protocol["applications"][0]["bid_price_text"] == "5200000"
    assert protocol["applications"][0]["contract_signed_flag_unverified"] is True
    assert protocol["winner_verified"] is False
    joined = link_original_documents(rows)
    assert len(joined["groups"]) == 1
    assert len(joined["groups"][0]["notices"]) == 2
    assert len(joined["groups"][0]["protocols"]) == 1
    assert joined["contract_price_verified"] is False


def test_invalid_initial_sum_and_inn_fail_closed(tmp_path):
    path, sha = _zip(tmp_path, {
        "notice.xml": _notice("purchaseNoticeZKESMBO", price="6 795 960", inn="not-valid"),
    })
    row = _source(path, sha)[0]
    assert row["customer_inn_evidence"] is None
    assert row["initial_lots"][0]["initial_sum_text"] is None
    assert row["winner_verified"] is False


@pytest.mark.parametrize("url", [
    "http://zakupki.gov.ru/223/purchase/public/download/download.html?id=12345678",
    "https://evil.example/223/purchase/public/download/download.html?id=12345678",
    "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=abc",
    "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=12345&secret=1",
    "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=12345#fragment",
    "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=xyz",
    "https://attacker@zakupki.gov.ru/223/purchase/public/download/download.html?id=12345678",
])
def test_untrusted_attachment_sources_denied(url):
    assert _public_filestore_digest(url) is None


def test_official_223_legacy_and_44_filestore_urls_only_hashes():
    old = "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=12345678"
    modern = ("https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/"
              "file.html?uid=ABCDEF1234567890ABCDEF1234567890")
    assert _public_filestore_digest(old) == hashlib.sha256(old.encode()).hexdigest()
    assert _public_filestore_digest(modern) == hashlib.sha256(modern.encode()).hexdigest()


def test_manifest_keeps_evidence_without_disclosing_download_query(tmp_path):
    url = "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=12345678"
    body = f"""<purchaseNoticeZKESMBO><body><item><purchaseNoticeZKESMBOData>
<registrationNumber>32313008364</registrationNumber>
<attachments><document><fileName>technical_spec.docx</fileName>
<url>{url}</url></document></attachments>
</purchaseNoticeZKESMBOData></item></body></purchaseNoticeZKESMBO>""".encode()
    path, sha = _zip(tmp_path, {"notice.xml": body})
    result = attachment_manifest(
        archive_path=path, official_archive_sha256=sha, subsystem="RI223",
        region="77", exact_date="2026-10-25",
    )
    assert result["safe_reference_count"] == 1
    assert result["records"][0]["extension"] == ".docx"
    assert result["records"][0]["document_downloaded"] is False
    assert "12345678" not in json.dumps(result)
    assert "download.html" not in json.dumps(result)


def test_manifest_source_sha_invalid_rejected(tmp_path):
    path, _ = _zip(tmp_path, {"notice.xml": _notice("purchaseNoticeZPESMBO")})
    with pytest.raises(ValueError, match="SHA-256"):
        attachment_manifest(
            archive_path=path, official_archive_sha256="1" * 64,
            subsystem="RI223", region="77", exact_date="2026-10-25",
        )


def test_committed_real_source_proofs_are_not_invented_awards():
    source = (
        Path(__file__).resolve().parents[1]
        / "data/market_intelligence/power_quality/official_primary_proofs_20261025.v1.json"
    )
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == "mi-pq-primary-source-proofs/0.1"
    assert snapshot["unique_procurements"] == len(snapshot["records"]) == 2
    assert snapshot["national_market_statistics_supported"] is False
    assert {row["registry_number"] for row in snapshot["records"]} == {
        "32313008364", "32615969197",
    }
    for row in snapshot["records"]:
        assert len(row["official_archive_sha256"]) == 64
        assert len(row["notice_source_xml_sha256"]) == 2
        assert len(row["protocol_source_xml_sha256"]) == 1
        assert all(len(hash_value) == 64 for hash_value in row["notice_source_xml_sha256"])
        assert row["initial_lot_currency"] == "RUB"
        assert row["source_grade"] == "official_original_xml_sha_verified_not_legal_award"
        assert row["winner_verified"] is False
        assert row["contract_signed_price_verified"] is False
    assert snapshot["winner_verified_count"] == 0
