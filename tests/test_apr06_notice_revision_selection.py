"""Regression from real Aksay and Moscow employment-centre EIS archive revisions."""
from __future__ import annotations

from src.modules.procurement_analysis.frozen_types import AnalyzedDocument
from src.modules.tender_operator_agent_demo.eis_notice_parser import (
    extract_notice_revision_info,
)
from src.modules.tender_operator_agent_demo.upload_service import (
    _enrich_procurement_metadata_from_documents,
)


def _xml(number: str, revision: int, deadline: str) -> str:
    return (
        "<export><epNotificationEZK2020>"
        f"<versionNumber>{revision}</versionNumber>"
        f"<commonInfo><purchaseNumber>{number}</purchaseNumber>"
        f"<publishDTInEIS>2026-10-{revision + 2:02d}T09:00:00+03:00</publishDTInEIS></commonInfo>"
        "<notificationInfo><contractConditionsInfo><maxPriceInfo>"
        "<maxPrice>152033.33</maxPrice></maxPriceInfo></contractConditionsInfo>"
        f"<procedureInfo><collectingInfo><endDT>{deadline}</endDT>"
        "</collectingInfo></procedureInfo></notificationInfo>"
        "</epNotificationEZK2020></export>"
    )


def _doc(number: str, version: int, deadline: str) -> AnalyzedDocument:
    raw = _xml(number, version, deadline)
    return AnalyzedDocument(
        display_name=f"epNotification_{number}_{version}.xml",
        extension=".xml",
        role="notice",
        text=raw,
        extracted_text_available=True,
        warnings=[],
        source="eis_soap",
        file_id=f"FILE-{version:02d}",
        raw_content=raw.encode(),
    )


def _enrich(number: str, docs: list[AnalyzedDocument]) -> dict:
    return _enrich_procurement_metadata_from_documents(
        {"procurement_id": number,
         "procurement": {"procurement_number": number},
         "mode": "procurement_search_intake"},
        documents=docs,
        combined_text=None,
        notice_text=docs[0].text,
        technical_spec_text=None,
        contract_draft_text=None,
    )


def test_aksay_never_uses_expired_v1_when_valid_v5_extends_submission():
    reg = "0158300034526000388"
    v1 = _doc(reg, 1, "2026-10-09T08:00:00+03:00")
    v5 = _doc(reg, 5, "2026-10-12T08:00:00+03:00")
    for ordered in ([v1, v5], [v5, v1]):
        actual = _enrich(reg, ordered)
        assert "12.10.2026" in str(actual["procurement"]["deadline"])
        assert "12.10.2026" in str(actual["deadline"])
        assert actual["notice_revision_selected"]["version"] == 5
        assert actual["notice_revision_selected"]["file_id"] == "FILE-05"


def test_moscow_czn_latest_v3_deadline_wins_despite_first_xml_order():
    reg = "0348100024426000039"
    actual = _enrich(
        reg,
        [
            _doc(reg, 1, "2026-10-16T10:00:00+03:00"),
            _doc(reg, 2, "2026-10-16T10:00:00+03:00"),
            _doc(reg, 3, "2026-10-19T10:00:00+03:00"),
        ],
    )
    assert "19.10.2026" in str(actual["procurement"]["deadline"])
    assert actual["notice_revision_selected"]["version"] == 3


def test_registry_mismatch_revision_cannot_override_own_notice():
    reg = "0158300034526000388"
    own = _doc(reg, 1, "2026-10-09T08:00:00+03:00")
    alien = _doc("0372200172326000015", 5, "2026-10-29T08:00:00+03:00")
    result = _enrich(reg, [own, alien])
    assert "09.10.2026" in str(result["deadline"])
    assert result["notice_revision_requires_review"] is True


def test_protocol_cancel_or_unidentified_xml_never_claims_authoritative_revision():
    text = (
        "<export><epNoticeApplicationCancel><commonInfo>"
        "<versionNumber>999</versionNumber>"
        "<purchaseNumber>0158300034526000388</purchaseNumber>"
        "</commonInfo></epNoticeApplicationCancel></export>"
    )
    assert extract_notice_revision_info(text) is None
    assert extract_notice_revision_info("<other><versionNumber>7</versionNumber></other>") is None
