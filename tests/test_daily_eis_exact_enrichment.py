"""Offline acceptance for official EIS exact-clock attestation and Daily Tender screening.

No external EIS access, PostgreSQL, user bid, portal POST or service restart.
"""
from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from src.modules.daily_tender_run import eis_detail_deadline as eis
from src.modules.daily_tender_run import service
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.schemas import DailyTenderProfile

REG = "0845500000526000021"
URL = (
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html"
    "?regNumber=" + REG
)
RUN = "DTR-20261123T050000Z-1a2b3c4d"


def html_detail(
    reg=REG, date="30.11.2026", clock="09:00", zone="МСК",
) -> str:
    return (
        f"<html><body><div>Извещение №{reg}</div>"
        '<span class="section__title">Дата и время окончания срока подачи заявок</span>'
        f'<span class="section__info">{date} {clock} '
        f"<span class='timeZoneName' title='official zone'>({zone})</span></span>"
        "<span class='cardMainInfo__title'>Окончание подачи заявок</span>"
        "<span class='cardMainInfo__content'>30.11.2026</span>"
        "</body></html>"
    )


@pytest.mark.parametrize(("zone", "date", "clock", "expected"), [
    ("МСК", "30.11.2026", "09:00", "2026-11-30T06:00:00+00:00"),
    ("МСК+7", "14.10.2026", "08:00", "2026-10-13T22:00:00+00:00"),
    ("МСК-1", "30.11.2026", "10:00", "2026-11-30T08:00:00+00:00"),
    ("МСК", "26.11.2026", "00:00", "2026-11-25T21:00:00+00:00"),
])
def test_explicit_clock_and_regional_offset_only(zone, date, clock, expected):
    actual, label = eis.parse_official_detail(html_detail(date=date, clock=clock, zone=zone), REG)
    assert actual.isoformat() == expected
    assert label == zone


@pytest.mark.parametrize("bad_html", [
    f"<html>{REG} <span class='cardMainInfo__content'>30.11.2026</span></html>",
    html_detail(clock=""),
    html_detail(zone="UTC"),
    html_detail(zone="МСК+15"),
    html_detail(reg="9999999999999999999"),
    html_detail() + html_detail(),
])
def test_unverified_or_date_only_html_cannot_invent_deadline(bad_html):
    with pytest.raises(eis.EISProofError):
        eis.parse_official_detail(bad_html, REG)


@pytest.mark.parametrize("bad", [
    "http://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=" + REG,
    "https://not-zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=" + REG,
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=999",
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html",
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=" + REG + "&extra=true",
    "https://zakupki.gov.ru/epz/order/notice/223/view/common-info.html?regNumber=" + REG,
])
def test_exact_first_party_url_or_fail_closed(bad):
    with pytest.raises(eis.EISProofError):
        eis._official_url(bad, REG)


class _Response:
    def __init__(self, raw: bytes, status=200, content_type="text/html; charset=utf-8"):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.buf = io.BytesIO(raw)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.buf.close()

    def read(self, count):
        return self.buf.read(count)


def _fake_source(monkeypatch, page: str, *, status=200, content_type="text/html"):
    calls = []
    raw = page.encode()

    class FakeOpener:
        def open(self, request, timeout):
            calls.append({"method": request.get_method(), "timeout": timeout, "url": request.full_url})
            return _Response(raw, status=status, content_type=content_type)

    monkeypatch.setattr(eis.urllib.request, "build_opener", lambda *args: FakeOpener())
    return calls


def test_https_detail_is_archived_0600_before_precise_deadline(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    calls = _fake_source(monkeypatch, html_detail(zone="МСК+2", clock="10:00"))
    proof, reason = eis.verify_official_eis_deadline(URL, REG, RUN, evidence_root=root)
    assert reason == "deadline_eis_exact_source_verified"
    assert proof is not None
    assert proof.deadline_utc == datetime(2026, 11, 30, 5, 0, tzinfo=UTC)
    assert proof.official_timezone == "МСК+2"
    assert calls == [{"method": "GET", "timeout": eis.HTTP_TIMEOUT_SECONDS, "url": URL}]
    folder = root / RUN
    assert folder.stat().st_mode & 0o777 == 0o700
    raw = (folder / (REG + ".html")).read_bytes()
    receipt = json.loads((folder / (REG + ".json")).read_text())
    assert receipt["html_sha256"] == proof.original_sha256 == eis._sha(raw)
    assert receipt["deadline_utc"] == proof.deadline_utc.isoformat()
    assert (folder / (REG + ".html")).stat().st_mode & 0o777 == 0o600
    assert (folder / (REG + ".json")).stat().st_mode & 0o777 == 0o600

    # Re-fetching the identical published original within the same run is safe.
    again, status = eis.verify_official_eis_deadline(URL, REG, RUN, evidence_root=root)
    assert again is not None
    assert status == "deadline_eis_exact_source_verified"
    assert len(calls) == 2

    _fake_source(monkeypatch, html_detail(clock="11:00"))
    changed, status = eis.verify_official_eis_deadline(URL, REG, RUN, evidence_root=root)
    assert changed is None and status == "deadline_eis_exact_source_unverified"
    assert eis._sha((folder / (REG + ".html")).read_bytes()) == receipt["html_sha256"]


def test_archive_missing_means_no_network_and_no_precise_deadline(monkeypatch):
    monkeypatch.delenv("ARVECTUM_DAILY_EIS_EVIDENCE_ROOT", raising=False)
    monkeypatch.setattr(
        eis.urllib.request, "build_opener",
        lambda *args: pytest.fail("must not fetch without a private source archive"),
    )
    proof, reason = eis.verify_official_eis_deadline(URL, REG, RUN)
    assert proof is None and reason == "deadline_eis_evidence_archive_not_configured"


@pytest.mark.parametrize("over", [
    ("text/plain", 200),
    ("text/html", 503),
])
def test_invalid_response_never_sets_deadline(tmp_path, monkeypatch, over):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    _fake_source(monkeypatch, html_detail(), content_type=over[0], status=over[1])
    proof, reason = eis.verify_official_eis_deadline(URL, REG, RUN, evidence_root=root)
    assert proof is None and reason == "deadline_eis_exact_source_unverified"
    assert not list(root.glob("**/*.html"))


def _screened_item(session, *, deadline: datetime | None = None):
    profile = DailyTenderProfile(
        profile_id="eis-clock-test", version="1", queries=["разработка"],
        max_deep_analysis=1,
        include_keywords=["разработ"],
        exclude_keywords=[],
        require_include_keyword=True,
        analysis_use_llm=False, synthesis_use_llm=False,
    )
    run = DailyTenderRun(
        run_id=RUN, profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_snapshot_json=profile.model_dump(mode="json"),
        status="RUNNING", current_stage="SCREEN", counts_json={},
    )
    session.add(run)
    session.add(DailyTenderRunItem(
        run_id=RUN, registry_number=REG,
        law="44fz", source="public_eis_html_44fz",
        source_url=URL, title="Разработка программного обеспечения MAX",
        customer_name="Тестовый заказчик", nmck_amount=550_000.0,
        deadline_at=deadline, source_fingerprint="synthetic-fingerprint",
        query_hits_json=["разработка"], stage="DISCOVER",
        status="DISCOVERED", screening_reasons_json=[],
    ))
    session.commit()
    return run, profile


def test_screen_rechecks_only_relevant_date_only_shortlist(session, monkeypatch):
    run, profile = _screened_item(session)
    when = datetime.now(UTC) + timedelta(days=2)
    proof = eis.EISDeadlineProof(when, "МСК+2", "a" * 64, datetime.now(UTC))
    seen = []
    monkeypatch.setattr(
        service, "verify_official_eis_deadline",
        lambda url, registry, run_id: (seen.append((url, registry, run_id)) or proof,
                                       "deadline_eis_exact_source_verified"),
    )
    service._screen(session, run, profile)
    saved = session.query(DailyTenderRunItem).filter_by(run_id=RUN).one()
    assert seen == [(URL, REG, RUN)]
    assert saved.status == "SHORTLISTED"
    assert "deadline_eis_exact_source_verified" in saved.screening_reasons_json
    assert "deadline_eis_source_timezone:МСК+2" in saved.screening_reasons_json
    assert f"deadline_eis_original_sha256:{'a' * 64}" in saved.screening_reasons_json
    assert "deadline_unknown" not in saved.screening_reasons_json


def test_screen_rejects_exact_expired_official_detail(session, monkeypatch):
    run, profile = _screened_item(session)
    proof = eis.EISDeadlineProof(
        datetime.now(UTC) - timedelta(days=1), "МСК", "b" * 64, datetime.now(UTC)
    )
    monkeypatch.setattr(
        service, "verify_official_eis_deadline",
        lambda *_args: (proof, "deadline_eis_exact_source_verified"),
    )
    service._screen(session, run, profile)
    saved = session.query(DailyTenderRunItem).filter_by(run_id=RUN).one()
    assert saved.status == "SCREENED_OUT"
    assert "application_deadline_expired" in saved.screening_reasons_json
    assert "deadline_eis_exact_source_verified" in saved.screening_reasons_json


def test_screen_preserves_unknown_and_manager_review_when_eis_unavailable(
    session, monkeypatch,
):
    run, profile = _screened_item(session)
    monkeypatch.setattr(
        service, "verify_official_eis_deadline",
        lambda *_args: (None, "deadline_eis_exact_source_unverified"),
    )
    service._screen(session, run, profile)
    saved = session.query(DailyTenderRunItem).filter_by(run_id=RUN).one()
    assert saved.status == "SHORTLISTED"
    assert saved.deadline_at is None
    assert "deadline_eis_exact_source_unverified" in saved.screening_reasons_json
    assert "deadline_unknown" in saved.screening_reasons_json
