"""Keep official public EIS CZN v4 evidence source-bound and non-commercial."""
from __future__ import annotations

import json
import re
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "docs/acceptance/apr06_czn_v4_public_eis_source_receipts_2026-10-13.json"
)


def test_official_html_version_4_is_not_promoted_to_original_eis_xml_truth():
    obj = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert obj["schema_version"] == "apr06-czn-v4-public-html-source-receipt-v1"
    assert obj["reg_number"] == "0348100024426000039"
    info = obj["official_public_html_evidence"]
    assert info["official_page_readable_from_ru_direct_ip"] is True
    assert info["notice_version"] == 4
    assert info["notice_version_state"] == "Действующая"
    assert info["previous_version"] == 3
    assert info["previous_version_state"] == "Недействующая"
    assert info["application_deadline_msk"] == "2026-10-23T10:00:00+03:00"
    source = obj["source_evidence"]
    assert source["official_v4_html_document_uid_count"] == 7
    assert source["official_v4_html_uids_with_matching_local_sha256_bytes"] == 7
    assert source["new_direct_v4_uid_downloads"] == 4
    assert source["reused_original_v3_uids"] == 3
    assert source["original_v4_epnotification_xml_acquired"] is False
    assert source["original_v4_epnotification_xml_sha256_verified"] is False
    assert source["official_v4_xml_attachment_size_binding_verified"] is False
    assert source["zip_internal_document_review_completed"] is False
    assert source["legal_or_commercial_acceptance"] is False
    assert source["human_gold_labels"] == 0


def test_seven_original_uid_receipts_are_unique_and_hash_well_formed():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    items = data["files"]
    assert len(items) == 7
    assert len({row["uid"] for row in items}) == 7
    assert sum(x["new_public_download"] for x in items) == 4
    assert all(re.fullmatch(r"[A-F0-9]{32}", x["uid"]) for x in items)
    assert all(re.fullmatch(r"[a-f0-9]{64}", x["sha256"]) for x in items)
    assert all(x["size_bytes"] > 100 for x in items)
    assert all(x["magic_signature_checked_in_this_run"] is True
               for x in items if x["new_public_download"])
    assert all(not x["new_public_download"]
               for x in items if "reused_archived_v3" in x["origin"])
