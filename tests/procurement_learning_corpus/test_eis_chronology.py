"""Prevent application-specific EIS post-final notices from rewriting tender outcomes."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.procurement_llm import audit_eis_chronology as m


def _fixtures(tmp_path: Path, monkeypatch, *,
              notice_app: str = m.OTHER_APP,
              notice_time: str = "2026-10-14T11:54:29+03:00",
              notice_proc: str = m.AKSAY,
              notice_rank: str = "14",
              full_proc: str = m.AKSAY):
    path = tmp_path / "original.zip"
    entries = [
        (
            '<applicationInfo><appNumber>122031738</appNumber>'
            '<appRating>38</appRating><finalPrice>119000</finalPrice>'
            '<admissionResultsInfo><admissionResultInfo><admitted>true</admitted>'
            '</admissionResultInfo></admissionResultsInfo></applicationInfo>'
        ),
        (
            '<applicationInfo><appNumber>122034518</appNumber>'
            '<appRating>14</appRating><finalPrice>57000</finalPrice>'
            '<admissionResultsInfo><admissionResultInfo><admitted>true</admitted>'
            '</admissionResultInfo></admissionResultsInfo></applicationInfo>'
        ),
    ]
    for i in range(53):
        entries.append(
            f'<applicationInfo><appNumber>other{i}</appNumber>'
            f'<appRating>{i + 40}</appRating><finalPrice>{30000+i}</finalPrice>'
            '<admissionResultsInfo><admissionResultInfo><admitted>true</admitted>'
            '</admissionResultInfo></admissionResultsInfo></applicationInfo>'
        )
    final = (
        f'<export><purchaseNumber>{full_proc}</purchaseNumber>'
        '<publishDTInEIS>2026-10-14T11:26:58+03:00</publishDTInEIS>'
        + "".join(entries) + '</export>'
    ).encode()
    notice = (
        f'<export><purchaseNumber>{notice_proc}</purchaseNumber>'
        f'<docPublishDTInEIS>{notice_time}</docPublishDTInEIS>'
        f'<applicationInfo><appNumber>{notice_app}</appNumber>'
        f'<appRating>{notice_rank}</appRating></applicationInfo>'
        '<protocolNumber>1</protocolNumber></export>'
    ).encode()
    with ZipFile(path, "w") as z:
        z.writestr(f'epProtocolEZK2020Final_{m.AKSAY}_fixture.xml', final)
        z.writestr(f'epNoticeApplicationCancel_{m.AKSAY}_fixture.xml', notice)
    monkeypatch.setattr(m, "ZIP_SHA", sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(m, "FINAL_XML_SHA", sha256(final).hexdigest())
    monkeypatch.setattr(m, "NOTICE_XML_SHA", sha256(notice).hexdigest())
    return path


def test_audit_application_specific_not_whole_tender(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch)
    out = m.audit_aksay_postfinal(f)
    assert out["company_application_number"] == m.OUR_APP
    assert out["company_original_final_app_rating"] == "38"
    assert out["notice_application_number"] == m.OTHER_APP
    assert out["notice_targets_company_application"] is False
    assert out["whole_procurement_cancelled_proven_by_notice"] is False
    assert out["new_ranking_after_notice_verified"] is False
    assert out["training_label_approved"] is False
    assert out["mutations"] == 0
    assert out["new_postgresql_records"] == 0


def test_notice_for_our_application_cannot_be_described_as_third_party(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch, notice_app=m.OUR_APP)
    with pytest.raises(ValueError, match="Unexpected application-level notice target"):
        m.audit_aksay_postfinal(f)


def test_wrong_procurement_in_notice_fails_closed(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch, notice_proc="0123456789012345678")
    with pytest.raises(ValueError, match="Mismatched procurement"):
        m.audit_aksay_postfinal(f)


def test_wrong_application_rating_fails_closed(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch, notice_rank="38")
    with pytest.raises(ValueError, match="Unexpected application-level notice target"):
        m.audit_aksay_postfinal(f)


def test_notice_before_final_cannot_be_misordered(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch, notice_time="2026-10-14T11:26:00+03:00")
    with pytest.raises(ValueError, match="does not follow"):
        m.audit_aksay_postfinal(f)


def test_timezone_less_notice_rejected(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch, notice_time="2026-10-14T11:54:29")
    with pytest.raises(ValueError, match="explicit timezone"):
        m.audit_aksay_postfinal(f)


def test_original_sha_tampered_is_rejected(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch)
    with f.open("ab") as fd:
        fd.write(b"tamper")
    with pytest.raises(ValueError, match="archive ZIP SHA"):
        m.audit_aksay_postfinal(f)


def test_symlink_source_rejected(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch)
    link = tmp_path / "alias.zip"
    link.symlink_to(f)
    with pytest.raises(ValueError, match="unsafe EIS archive"):
        m.audit_aksay_postfinal(link)


def test_original_application_count_must_match(tmp_path, monkeypatch):
    f = _fixtures(tmp_path, monkeypatch)
    with ZipFile(f) as z:
        members = {i.filename: z.read(i) for i in z.infolist()}
    for name, content in members.items():
        if name.startswith("epProtocolEZK2020Final"):
            content = content.replace(b"<appNumber>other52</appNumber>", b"<appNumber>122031738</appNumber>")
            members[name] = content
            monkeypatch.setattr(m, "FINAL_XML_SHA", sha256(content).hexdigest())
    with ZipFile(f, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    monkeypatch.setattr(m, "ZIP_SHA", sha256(f.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="Duplicate or missing appNumber"):
        m.audit_aksay_postfinal(f)
