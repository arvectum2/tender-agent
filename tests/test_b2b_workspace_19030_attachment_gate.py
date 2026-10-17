"""Original public file listing is NOT permission to fetch a PRO-gated private PDF."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.acceptance.audit_workspace_19030_attachment_gate import (
    ACCESS_NOTICE,
    ORIGINAL_URL,
    evaluate_original,
)

ROOT = Path(__file__).resolve().parents[1] / "docs" / "roadmap"
DATA = json.loads((ROOT / "b2b_workspace_19030_attachment_access_2026-10-17.json").read_text())
NOW = datetime(2026, 10, 17, 20, 30, tzinfo=UTC)


def html(*, gate=ACCESS_NOTICE, filename="TZ_.pdf", status="Идет прием заявок",
         extra="", deadline="13 ноября 2026"):
    return (f'<html><h1>Внедрение ИИ-системы учёта производства</h1>'
            f'<div class="tendercart-type__status-public">{status}</div>'
            '<div class="reference _public"></div>'
            'Oрганизатор <span>Юридическое лицо</span>'
            f'Крайний срок приема заявок: <span>{deadline}</span>'
            '<p>Подробное ТЗ во вложении.</p>'
            '<div class="tendercard__title">Файлы к тендеру</div>'
            f'<span>{gate}</span>'
            '<div class="tendercard__files">'
            f'<div class="tendercard__file" title="{filename}">'
            f'<div><span>{filename}</span></div>{extra}</div></div>'
            '<div class="tendercard__block _border-none"></div>'
            '</html>').encode()


def test_actual_source_attests_listing_and_explicit_gate_not_download():
    assert DATA["schema_version"] == "workspace-19030-first-party-attachment-gate-v1"
    assert DATA["source_url"] == ORIGINAL_URL
    assert DATA["original_source_http"] == 200
    assert len(DATA["source_html_sha256"]) == 64
    assert DATA["source_html_bytes"] > 50_000
    assert DATA["public_status"] == "Идет прием заявок"
    assert DATA["original_attachment_listed_name"] == "TZ_.pdf"
    assert DATA["original_access_rule"] == "PRO_ACCOUNT_OR_CUSTOMER_INVITATION"
    assert DATA["public_unauthenticated_direct_attachment_href_in_panel"] is False
    assert DATA["pdf_downloaded"] is False
    assert DATA["pdf_bytes_verified"] is False
    assert DATA["detailed_tz_text_read"] is False
    assert DATA["technical_scope_complete"] is False
    assert DATA["pilot_quote_authorized"] is False
    assert DATA["company_workspace_pro_or_invitation_verified"] is False
    assert DATA["owner_bid_go"] is False
    assert DATA["outbound_actions_or_payments"] == 0
    assert datetime.fromisoformat(DATA["observed_at_utc"]).tzinfo is not None


def test_frozen_public_test_has_zero_private_actions():
    r = evaluate_original(html(), observed_at=NOW)
    assert r["pdf_downloaded"] is False
    assert r["company_bid_eligibility_state"] == "LLC_REVIEW_REQUIRED"
    assert r["outbound_actions_or_payments"] == 0


@pytest.mark.parametrize(("case", "reason"), [
    ({"gate": "Загрузите файл"}, "wording changed"),
    ({"filename": "other.pdf"}, "not attested"),
    ({"extra": '<a href="/private/files/19030">open</a>'}, "panel changed"),
    ({"status": "Завершён"}, "no longer currently accepting"),
    ({"deadline": "14 ноября 2026"}, "deadline"),
])
def test_source_drift_does_not_turn_hidden_document_into_verified_scope(case, reason):
    with pytest.raises(ValueError, match=reason):
        evaluate_original(html(**case), observed_at=NOW)


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError, match="timezone"):
        evaluate_original(html(), observed_at=NOW.replace(tzinfo=None))
