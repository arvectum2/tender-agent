"""Fresh official XML and changed-file proof; no network calls in pytest."""
from __future__ import annotations

import copy
import json
import os
import zipfile
from pathlib import Path

import pytest

from scripts.acceptance.build_r4_official_current_freshness import (
    notice_attachments,
    readable_freshness,
    same_deadline,
    verified_current_sources,
)


def test_current_xml_deadline_timezone_and_unknown():
    assert same_deadline("2026-10-16T09:00:00+07:00", "2026-10-16T05:00:00+03:00")
    assert not same_deadline("2026-10-19T10:00:00+03:00", "2026-10-23T10:00:00+03:00")
    assert same_deadline(None, "2026-10-23T10:00:00+03:00") is None


def test_original_attachment_identity_never_guessed(tmp_path: Path):
    p = tmp_path / "archive.zip"
    xml = (
        '<root><epNotificationEOK2020>'
        '<versionNumber>4</versionNumber><purchaseNumber>0348100024426000039</purchaseNumber>'
        '<attachmentsInfo><attachmentInfo><publishedContentId>unit-01</publishedContentId>'
        '<fileName>contract.zip</fileName><fileSize>120</fileSize></attachmentInfo></attachmentsInfo>'
        '</epNotificationEOK2020></root>'
    )
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("notice.xml", xml)
    a = notice_attachments(p, "0348100024426000039", 4)
    assert a["unit-01"]["fileName"] == "contract.zip"
    with pytest.raises(ValueError, match="ambiguous"):
        notice_attachments(p, "0348100024426000039", 3)
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(
            "notice.xml",
            xml.replace(
                "</attachmentInfo></attachmentsInfo>",
                "</attachmentInfo><attachmentInfo>"
                "<publishedContentId>unit-01</publishedContentId>"
                "<fileName>duplicate.docx</fileName>"
                "</attachmentInfo></attachmentsInfo>",
            ),
        )
    with pytest.raises(ValueError):
        notice_attachments(p, "0348100024426000039", 4)


def _private_originals():
    root = os.environ.get("TA_PRIVATE_R4_SOURCE_ROOT")
    if not root:
        pytest.skip("current first-party EIS ZIP evidence private to Mac mini")
    source = Path(root)
    current = source / "ai-expert-20261014" / "live-official-xml-batch-20261014"
    changed = current / "0348100024426000039" / "new-v4-attachments"
    path = Path("docs/acceptance/data")
    return {
        "archived": json.loads(
            (path / "TDP_R4_20_TRUE_COMPETITIVE_ORIGINAL_SEMANTIC_AUDIT_2026-10-14.json").read_text()
        ),
        "soap_receipt": json.loads(
            (current / "official-live-xml20-private-receipt.json").read_text()
        ),
        "html": json.loads(
            (path / "TDP_R4_20_LIVE_OFFICIAL_EIS_CARDS_2026-10-14.json").read_text()
        ),
        "fresh_root": current,
        "old_root": source / "official-revision-batch-20261011",
        "binary_receipt": json.loads(
            (changed / "changed-v4-firstparty-receipt.json").read_text()
        ),
        "binary_dir": changed,
    }


def test_original_20_soap_sources_edited_attachments_not_mistaken_for_old():
    data = verified_current_sources(**_private_originals())
    assert data["verified_official_xml_cases"] == 20
    assert data["official_html_stage_attested"] == 2
    assert data["changed_xml_versions"] == ["0348100024426000039"]
    assert data["deadlines_changed"] == 1
    assert data["after_check_future_deadlines"] == 5
    assert data["signed_expert_reviews"] == 0
    assert data["bid_ready"] is False
    case = next(v for v in data["cases"]
                if v["registry_number"] == "0348100024426000039")
    assert case["archived_version"] == 3 and case["current_official_xml_version"] == 4
    assert case["current_official_xml_endDT"] == "2026-10-23T10:00:00+03:00"
    assert case["unchanged_attachment_refs"] == 3
    assert len(case["new_replaced_attachments"]) == 4
    assert len(case["identical_inner_payloads"]) == 1
    assert len(case["identical_inner_payloads"][0]["source_locations"]) == 2
    assert case["old_semantic_review_is_stale"]
    assert all(v["binary_verified"] and not v["full_legal_scope_review_signed"]
               for v in case["new_replaced_attachments"])
    assert "Подписано экспертных заключений" in readable_freshness(data)


def test_original_source_and_html_discrepancies_fail_closed():
    a = _private_originals()
    altered = copy.deepcopy(a)
    next(v for v in altered["soap_receipt"]
         if v["registry_number"] == "0348100024426000039")["source_zip_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="ZIP/XML"):
        verified_current_sources(**altered)

    altered = copy.deepcopy(a)
    next(v for v in altered["html"]["cases"]
         if v["registry_number"] == "0348100024426000039")["displayed_deadline"] = (
             "19.10.2026 10:00 (МСК)"
         )
    with pytest.raises(ValueError, match="deadlines disagree"):
        verified_current_sources(**altered)

    altered = copy.deepcopy(a)
    altered["binary_receipt"][0]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="SHA/size"):
        verified_current_sources(**altered)
