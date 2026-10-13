"""EIS source regression: archived notice v5/v3 must win over stale v1 cards.

The highest archived revision still needs independent live EIS confirmation.
"""

from __future__ import annotations

import json

import pytest

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.operator_notice_revision import (
    matched_archived_eis_notification,
    selected_archived_notice_text,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    _enrich_procurement_metadata_from_documents,
)


def _xml(number: str, version: int, deadline: str) -> str:
    return (
        "<export><epNotificationEZK2020>"
        f"<versionNumber>{version}</versionNumber>"
        "<commonInfo>"
        f"<purchaseNumber>{number}</purchaseNumber>"
        f"<publishDTInEIS>2026-10-{version + 2:02d}T09:00:00+03:00</publishDTInEIS>"
        "</commonInfo><notificationInfo><procedureInfo><collectingInfo>"
        f"<endDT>{deadline}</endDT>"
        "</collectingInfo></procedureInfo></notificationInfo>"
        "</epNotificationEZK2020></export>"
    )


def _doc(number: str, version: int, deadline: str) -> AnalyzedDocument:
    raw = _xml(number, version, deadline)
    return AnalyzedDocument(
        display_name=f"epNotification_{number}_v{version}.xml",
        extension=".xml",
        role="notice",
        text=raw,
        extracted_text_available=True,
        warnings=[],
        source="eis_soap",
        file_id=f"FILE-{version:02d}",
        raw_content=raw.encode(),
    )


def _enrich(number: str, docs: list[AnalyzedDocument], card_deadline: str):
    return _enrich_procurement_metadata_from_documents(
        {
            "procurement_id": number,
            "procurement_source": "zakupki_gov_ru_getdocs_ip",
            "mode": "procurement_search_intake",
            "deadline": card_deadline,
            "procurement": {
                "procurement_number": number,
                "deadline": card_deadline,
            },
        },
        documents=docs,
        combined_text=None,
        notice_text=docs[0].text,
        technical_spec_text=None,
        contract_draft_text=None,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_aksay_v5_supersedes_expired_v1_and_stale_card(reverse):
    number = "0158300034526000388"
    v1 = _doc(number, 1, "2026-10-09T08:00:00+03:00")
    v5 = _doc(number, 5, "2026-10-12T08:00:00+03:00")
    docs = [v5, v1] if reverse else [v1, v5]
    result = _enrich(number, docs, "09.10.2026 08:00:00 +03:00")
    assert "12.10.2026" in str(result["deadline"])
    assert "12.10.2026" in str(result["procurement"]["deadline"])
    assert result["notice_revision_selected"]["version"] == 5
    assert result["notice_revision_selected"]["file_id"] == "FILE-05"
    assert result["notice_revision_selected"]["current_live_eis_verified"] is False
    assert result["notice_revision_requires_review"] is True
    assert any("не доказывает актуальность" in note for note in result["limitations"])
    assert result["_field_evidence"]["application_deadline"] == "eis_notice:submission_deadline"


def test_moscow_czn_v3_supersedes_expired_v1_and_card():
    number = "0348100024426000039"
    docs = [
        _doc(number, 1, "2026-10-16T10:00:00+03:00"),
        _doc(number, 2, "2026-10-16T10:00:00+03:00"),
        _doc(number, 3, "2026-10-19T10:00:00+03:00"),
    ]
    result = _enrich(number, docs, "16.10.2026 10:00:00 +03:00")
    assert "19.10.2026" in str(result["deadline"])
    assert result["notice_revision_selected"]["version"] == 3


def test_alien_higher_version_cannot_override_exact_registry():
    number = "0158300034526000388"
    own = _doc(number, 1, "2026-10-09T08:00:00+03:00")
    alien = _doc("0372200172326000015", 9, "2026-10-29T08:00:00+03:00")
    result = _enrich(number, [own, alien], "09.10.2026 08:00:00 +03:00")
    assert "09.10.2026" in str(result["deadline"])
    assert result["notice_revision_selected"]["version"] == 1
    assert result["notice_revision_requires_review"] is True


def test_protocol_or_cancellation_version_number_not_authoritative():
    number = "0158300034526000388"
    fake = (
        "<export><epNoticeApplicationCancel><commonInfo>"
        f"<purchaseNumber>{number}</purchaseNumber><versionNumber>999</versionNumber>"
        "</commonInfo><notificationInfo><endDT>2026-10-30T08:00:00+03:00</endDT>"
        "</notificationInfo></epNoticeApplicationCancel></export>"
    )
    assert matched_archived_eis_notification(fake, number) is None
    assert matched_archived_eis_notification("<other><versionNumber>5</versionNumber></other>", number) is None


def test_unversioned_xml_never_claims_confirmed_notice_revision():
    number = "0158300034526000388"
    plain = (
        "<notice>"
        f"<purchaseNumber>{number}</purchaseNumber>"
        "<endDT>2026-10-09T08:00:00+03:00</endDT>"
        "</notice>"
    )
    document = AnalyzedDocument(
        display_name="simple_notice.xml",
        extension=".xml",
        role="notice",
        text=plain,
        extracted_text_available=True,
        warnings=[],
        source="eis_soap",
        file_id="RAW",
        raw_content=plain.encode(),
    )
    result = _enrich(number, [document], "09.10.2026 08:00:00 +03:00")
    assert result.get("notice_revision_selected") is None
    assert result["notice_revision_requires_review"] is True


def test_doctype_or_entity_cannot_authorize_revision():
    number = "0158300034526000388"
    raw = (
        "<!DOCTYPE foo [ <!ENTITY x SYSTEM 'file:///etc/passwd'> ]>"
        + _xml(number, 9, "2026-10-30T08:00:00+03:00")
    )
    assert matched_archived_eis_notification(raw, number) is None


def test_version_from_common_info_if_direct_child_missing():
    number = "0158300034526000388"
    raw = (
        "<export><epNotificationEZK2020><commonInfo>"
        f"<purchaseNumber>{number}</purchaseNumber>"
        "<versionNumber>3</versionNumber>"
        "</commonInfo></epNotificationEZK2020></export>"
    )
    rev = matched_archived_eis_notification(raw, number)
    assert rev is not None and rev["version"] == 3


@pytest.mark.parametrize("reverse", [False, True])
def test_latest_archived_version_is_only_notice_text_sent_to_analysis(reverse):
    number = "0158300034526000388"
    v1 = _doc(number, 1, "2026-10-09T08:00:00+03:00")
    v5 = _doc(number, 5, "2026-10-12T08:00:00+03:00")
    docs = [v5, v1] if reverse else [v1, v5]
    result = _enrich(number, docs, "09.10.2026 08:00:00 +03:00")
    selected = selected_archived_notice_text(docs, result["notice_revision_selected"])
    assert selected == v5.text
    assert "2026-10-12T08:00:00+03:00" in selected
    assert "2026-10-09T08:00:00+03:00" not in selected


def test_forged_selection_does_not_route_older_text_as_current_revision():
    number = "0158300034526000388"
    v1 = _doc(number, 1, "2026-10-09T08:00:00+03:00")
    assert selected_archived_notice_text(
        [v1],
        {
            "purchase_number": number,
            "version": 5,
            "file_id": "FILE-01",
        },
    ) is None
    assert selected_archived_notice_text(
        [v1],
        {
            "purchase_number": "0372200172326000015",
            "version": 1,
            "file_id": "FILE-01",
        },
    ) is None


def test_uploaded_archived_notices_route_latest_version_to_llm_prompt(
    client, tmp_path, monkeypatch
):
    from src.modules.tender_operator_agent_demo import upload_service_legacy as legacy

    number = "0158300034526000388"
    root = tmp_path / "eis_revision_run"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))
    seen_notices = []

    def capture_notice(**kwargs):
        seen_notices.append(kwargs.get("notice_text", ""))

    monkeypatch.setattr(legacy, "_try_run_llm_workflow", capture_notice)

    old_xml = _xml(number, 1, "2026-10-09T08:00:00+03:00").encode()
    new_xml = _xml(number, 5, "2026-10-12T08:00:00+03:00").encode()
    response = client.post(
        "/api/demo/tender-agent/runs",
        data={
            "tender_title": "Закупка",
            "tender_category": "Услуги",
            "customer_name": "Заказчик",
        },
        files=[
            ("files", ("notice_v1.xml", old_xml, "application/xml")),
            ("files", ("notice_v5.xml", new_xml, "application/xml")),
            (
                "files",
                ("technical_spec.txt", b"Requirements from customer.", "text/plain"),
            ),
            (
                "files",
                ("contract_draft.txt", b"Contract obligations.", "text/plain"),
            ),
        ],
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    metadata_path = root / run_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["procurement_id"] = number
    metadata["mode"] = "procurement_search_intake"
    metadata["procurement_source"] = "zakupki_gov_ru_getdocs_ip"
    metadata["procurement"] = {
        "procurement_number": number,
        "deadline": "09.10.2026 08:00:00 +03:00",
    }
    metadata["deadline"] = "09.10.2026 08:00:00 +03:00"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False))

    analyzed = client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze")
    assert analyzed.status_code == 200
    assert analyzed.json()["status"] != "failed"
    assert len(seen_notices) == 1
    assert "2026-10-12T08:00:00+03:00" in seen_notices[0]
    assert "2026-10-09T08:00:00+03:00" not in seen_notices[0]
    metadata = json.loads(metadata_path.read_text())
    assert metadata["notice_revision_selected"]["version"] == 5
    assert metadata["notice_revision_requires_review"] is True
