from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_source_ledger import (
    extract_archive,
    link_original_documents,
)


def _notice(number: str = "32616447910") -> bytes:
    return f"""<purchaseNotice>
<body><item><purchaseNoticeData>
<registrationNumber>{number}</registrationNumber>
<name>Комплексная модернизация подстанции</name>
</purchaseNoticeData></item></body></purchaseNotice>""".encode()


def _protocol(number: str = "32616447910", price: str = "9500000.00") -> bytes:
    return f"""<purchaseProtocol><body><item><purchaseProtocolData>
<purchaseInfo><purchaseNoticeNumber>{number}</purchaseNoticeNumber></purchaseInfo>
<registrationNumber>PROT-123</registrationNumber>
<lotApplicationsList><protocolLotApplications>
<lot><ordinalNumber>1</ordinalNumber></lot>
<application>
<applicationNumber>4</applicationNumber>
<provider><mainInfo><inn>1234567890</inn></mainInfo></provider>
<price>{price}</price><currency><code>RUB</code></currency>
<accepted>true</accepted><considerationResultInfo><accepted>true</accepted></considerationResultInfo>
<contractSigned>true</contractSigned><rating>1</rating>
</application></protocolLotApplications></lotApplicationsList>
</purchaseProtocolData></item></body></purchaseProtocol>""".encode()


def _archive(path: Path, files: list[tuple[str, bytes]]) -> str:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files:
            z.writestr(name, data)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(path: Path, digest: str):
    return extract_archive(
        path, official_archive_sha256=digest,
        subsystem="RI223", region="77", exact_date="2026-10-08",
    )


def test_original_notice_protocol_join_and_no_unreviewed_winner(tmp_path: Path):
    path = tmp_path / "official.zip"
    sha = _archive(path, [("notice.xml", _notice()), ("protocol.xml", _protocol())])
    docs = _extract(path, sha)
    assert len(docs) == 2
    assert {row["record_kind"] for row in docs} == {"notice", "protocol"}
    assert all(row["source"]["official_archive_sha256"] == sha for row in docs)
    protocol = next(row for row in docs if row["record_kind"] == "protocol")
    assert protocol["notice_number"] == "32616447910"
    assert protocol["protocol_number"] == "PROT-123"
    app = protocol["applications"][0]
    assert app["provider_inn_evidence"] == "1234567890"
    assert app["accepted_flag"] is True
    assert app["contract_signed_flag_unverified"] is True
    assert app["bid_price_text"] == "9500000.00"
    assert app["winner_verified"] is False
    assert app["signed_contract_price_verified"] is False
    result = link_original_documents(docs)
    assert len(result["groups"]) == 1
    assert len(result["groups"][0]["notices"]) == 1
    assert len(result["groups"][0]["protocols"]) == 1
    assert result["winner_verified"] is False
    assert result["contract_price_verified"] is False


def test_exact_bytes_deduplicate_but_new_revision_preserved(tmp_path: Path):
    p = tmp_path / "revisions.zip"
    sha = _archive(p, [
        ("notice-v1.xml", _notice()),
        ("copy.xml", _notice()),
        ("notice-v2.xml", _notice().replace("подстанции".encode(), "электроцентрали".encode())),
    ])
    rows = _extract(p, sha)
    # Dedup via exact raw bytes SHA, not by procurement number.
    assert len(rows) == 2
    linked = link_original_documents(rows)
    assert len(linked["groups"]) == 1
    assert len(linked["groups"][0]["notices"]) == 2


def test_archive_or_xml_integrity_fail_closed(tmp_path: Path):
    path = tmp_path / "official.zip"
    sha = _archive(path, [("notice.xml", _notice())])
    with pytest.raises(ValueError, match="SHA-256"):
        _extract(path, "f" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        _extract(path, sha.replace("a", "0") if "a" in sha else "b" * 64)


@pytest.mark.parametrize("bad_member", [
    b'<!DOCTYPE foo [<!ENTITY x "bar">]><foo>&x;</foo>',
    b'<!ENTITY x "bar"><foo/>',
])
def test_xml_external_entity_rejected(tmp_path: Path, bad_member: bytes):
    path = tmp_path / "unsafe.zip"
    sha = _archive(path, [("evil.xml", bad_member)])
    with pytest.raises(ValueError, match="DTD"):
        _extract(path, sha)


def test_invalid_member_path_rejected(tmp_path: Path):
    path = tmp_path / "escape.zip"
    sha = _archive(path, [("../evil.xml", _notice())])
    with pytest.raises(ValueError, match="Unsafe ZIP"):
        _extract(path, sha)


def test_44fz_fallback_unidentified_notice_not_merged(tmp_path: Path):
    path = tmp_path / "44.xml.zip"
    sha = _archive(path, [("ep.xml", b"<epNotificationEF2020><unexpected>0</unexpected></epNotificationEF2020>")])
    docs = extract_archive(path, official_archive_sha256=sha, subsystem="PRIZ",
                           region="78", exact_date="2026-10-08")
    assert docs[0]["record_kind"] == "notice"
    assert docs[0]["notice_number"] is None
    result = link_original_documents(docs)
    assert result["unlinked_missing_notice_number"] == 1
    assert result["groups"] == []


def test_unverifiable_bid_price_does_not_become_contract_price(tmp_path: Path):
    path = tmp_path / "bad-price.zip"
    sha = _archive(path, [("protocol.xml", _protocol(price="9 500 000"))])
    app = _extract(path, sha)[0]["applications"][0]
    assert app["bid_price_text"] is None
    assert app["signed_contract_price_verified"] is False


def test_rejects_wrong_source_selector_and_sha(tmp_path: Path):
    path = tmp_path / "official.zip"
    sha = _archive(path, [("notice.xml", _notice())])
    with pytest.raises(ValueError, match="Invalid official source selector"):
        extract_archive(path, official_archive_sha256=sha, subsystem="XX", region="77",
                        exact_date="2026-10-08")
    with pytest.raises(ValueError, match="Invalid source digest"):
        _extract(path, "not a sha")

def test_real_44fz_export_wrapper_purchase_number(tmp_path: Path):
    original = b"""<export><epNotificationEF2020><commonInfo>
<purchaseNumber>0372200277526000545</purchaseNumber>
<docNumber>ABC-ORDER</docNumber>
</commonInfo></epNotificationEF2020></export>"""
    path = tmp_path / "wrapped.zip"
    sha = _archive(path, [("epNotificationEF2020_1.xml", original)])
    docs = extract_archive(
        path, official_archive_sha256=sha, subsystem="PRIZ",
        region="78", exact_date="2026-10-08",
    )
    assert len(docs) == 1
    assert docs[0]["xml_root"] == "epNotificationEF2020"
    assert docs[0]["transport_root"] == "export"
    assert docs[0]["notice_number"] == "0372200277526000545"
    assert docs[0]["winner_verified"] is False


def test_export_with_multiple_documents_does_not_guess_notice(tmp_path: Path):
    path = tmp_path / "ambiguous.zip"
    sha = _archive(path, [(
        "multi.xml",
        b"<export><epNotificationEF2020/><epNotificationEF2020/></export>",
    )])
    docs = extract_archive(
        path, official_archive_sha256=sha, subsystem="PRIZ",
        region="77", exact_date="2026-10-08",
    )
    assert docs[0]["record_kind"] == "other_primary_xml"
    assert docs[0]["notice_number"] is None

def test_44fz_original_final_protocols_are_linked_not_awarded(tmp_path: Path):
    number = "0373200026426000249"
    notice = f"""<export><epNotificationEF2020><commonInfo>
<purchaseNumber>{number}</purchaseNumber>
</commonInfo></epNotificationEF2020></export>""".encode()
    final = f"""<export><epProtocolEF2020Final>
<commonInfo><purchaseNumber>{number}</purchaseNumber><docNumber>FINAL-2026</docNumber></commonInfo>
<protocolInfo><applicationsInfo><applicationInfo><commonInfo><appNumber>7</appNumber></commonInfo>
<finalPrice>150000.00</finalPrice></applicationInfo></applicationsInfo></protocolInfo>
</epProtocolEF2020Final></export>""".encode()
    placement = f"""<export><fcsPlacementResult>
<purchaseNumber>{number}</purchaseNumber><foundationProtocolNumber>PLACEMENT-2026</foundationProtocolNumber>
<applications><application><journalNumber>1</journalNumber><price>149000.00</price></application></applications>
</fcsPlacementResult></export>""".encode()
    proposals = f"""<export><fcsProposalsResult>
<purchaseNumber>{number}</purchaseNumber><protocolNumber>PROPOSALS-2026</protocolNumber>
<applications><application><appNumber>3</appNumber><price>148000.00</price></application></applications>
</fcsProposalsResult></export>""".encode()
    path = tmp_path / "44fz-originals.zip"
    sha = _archive(path, [
        ("notice.xml", notice), ("final.xml", final),
        ("placement.xml", placement), ("proposals.xml", proposals),
    ])
    docs = extract_archive(
        path, official_archive_sha256=sha, subsystem="PRIZ",
        region="77", exact_date="2026-10-08",
    )
    assert len(docs) == 4
    protocols = [row for row in docs if row["record_kind"] == "protocol"]
    assert len(protocols) == 3
    assert all(row["notice_number"] == number for row in protocols)
    assert [row["applications"][0]["bid_price_text"] for row in protocols] == [
        "150000.00", "149000.00", "148000.00",
    ]
    assert all(not row["applications"][0]["winner_verified"] for row in protocols)
    linked = link_original_documents(docs)
    assert len(linked["groups"]) == 1
    assert len(linked["groups"][0]["protocols"]) == 3
    assert linked["winner_verified"] is False
    assert linked["contract_price_verified"] is False


def test_actual_eis_sized_large_application_group_is_bounded(tmp_path: Path):
    # Genuine 44-FZ protocols can contain 960 offers. Cap remains strict,
    # but must not reject real large events solely due to low fixture sizes.
    from src.modules.market_intelligence.eis_source_ledger import (
        MAX_APPLICATIONS_PER_PROTOCOL,
    )

    assert MAX_APPLICATIONS_PER_PROTOCOL >= 960
    too_many = "<application><appNumber>1</appNumber></application>" * (
        MAX_APPLICATIONS_PER_PROTOCOL + 1
    )
    payload = ("<fcsProposalsResult><purchaseNumber>0373200026426000249</purchaseNumber>"
               "<applications>" + too_many + "</applications></fcsProposalsResult>")
    path = tmp_path / "large-applications.zip"
    sha = _archive(path, [("proposals.xml", payload.encode())])
    with pytest.raises(ValueError, match="applications exceed bound"):
        extract_archive(
            path, official_archive_sha256=sha, subsystem="PRIZ",
            region="77", exact_date="2026-10-08",
        )

def test_kesmbo_notice_and_summingup_protocol_originals_are_linked_without_award(tmp_path: Path):
    number = "32616120582"
    notice = f"""<purchaseNoticeKESMBO><body><item><purchaseNoticeKESMBOData>
    <registrationNumber>{number}</registrationNumber>
    <customer><mainInfo><fullName>ПАО Россети Северо-Запад</fullName><inn>7802312751</inn></mainInfo></customer>
    <lots><lot><ordinalNumber>1</ordinalNumber><lotData>
    <subject>Монтаж УКРМ 6 кВ в составе EPC</subject><initialSum>21120361.66</initialSum>
    <currency><code>RUB</code></currency></lotData></lot></lots>
    </purchaseNoticeKESMBOData></item></body></purchaseNoticeKESMBO>""".encode()
    protocol = f"""<purchaseProtocolSummingupKESMBO><body><item>
    <purchaseProtocolSummingupKESMBOData><purchaseInfo>
    <purchaseNoticeNumber>{number}</purchaseNoticeNumber></purchaseInfo>
    <registrationNumber>{number}-04</registrationNumber>
    <lotApplicationsList><protocolLotApplications><lot><ordinalNumber>1</ordinalNumber></lot>
    <application><applicationNumber>4149972340</applicationNumber><price>17000000.0</price>
    <currency><code>RUB</code></currency><accepted>true</accepted>
    <contractSigned>true</contractSigned></application>
    </protocolLotApplications></lotApplicationsList>
    </purchaseProtocolSummingupKESMBOData></item></body></purchaseProtocolSummingupKESMBO>""".encode()
    p = tmp_path / "original-kesmbo.zip"
    sha = _archive(p, [("notice.xml", notice), ("protocol.xml", protocol)])
    docs = _extract(p, sha)
    notice_record = next(x for x in docs if x["record_kind"] == "notice")
    protocol_record = next(x for x in docs if x["record_kind"] == "protocol")
    assert notice_record["notice_number"] == protocol_record["notice_number"] == number
    assert notice_record["customer_inn_evidence"] == "7802312751"
    assert notice_record["initial_lots"][0]["initial_sum_text"] == "21120361.66"
    assert protocol_record["applications"][0]["bid_price_text"] == "17000000.0"
    assert protocol_record["applications"][0]["contract_signed_flag_unverified"] is True
    assert protocol_record["applications"][0]["winner_verified"] is False
    assert link_original_documents(docs)["winner_verified"] is False
