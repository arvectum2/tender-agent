"""Source-bound document triage; original EIS ZIP doesn't prove current GO."""
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs/roadmap"
EIS = json.loads((ROOT / "b2b_priority_eis_documents_2026-10-17.json").read_text())
WS = json.loads((ROOT / "b2b_priority_workspace_19041_2026-10-17.json").read_text())
DEC = json.loads((ROOT / "b2b_priority_three_matrix_2026-10-17.json").read_text())


def test_original_document_set_bounded_sha_and_all_fourteen_originals_retrieved():
    assert EIS["schema_version"] == "arvectum-44fz-original-attachments-source-review-v1"
    assert EIS["read_only"] is True
    assert EIS["official_original_binary_files_persisted"] is False
    assert EIS["official_live_legal_status_verified"] is False
    assert EIS["all_originals_text_fully_verified"] is False
    assert EIS["total_originals_verified_by_live_readonly"] == 14
    assert len(EIS["procedures"]) == 2
    assert {x["procurement_number"] for x in EIS["procedures"]} == {
        "0161600001326000063", "0816500000626015655",
    }
    for c in EIS["procedures"]:
        assert len(c["original_files"]) == 7
        assert c["successfully_retrieved_attachment_count"] == 7
        assert c["original_published_attachment_count"] == 7
        assert c["selected_archived_version"] == 1
        assert c["official_live_procedure_status_verified"] is False
        assert c["owner_bid_eligibility_verified"] is False
        assert re.fullmatch("[0-9a-f]{64}", c["zip_sha256"])
        assert re.fullmatch("[0-9a-f]{64}", c["notice_xml_sha256"])
        assert len({x["official_source_url_sha256"] for x in c["original_files"]}) == 7
        for f in c["original_files"]:
            assert f["retrieved"] is True
            assert f["original_bytes"] > 400
            assert re.fullmatch("[0-9a-f]{64}", f["sha256"])
            assert re.fullmatch("[0-9a-f]{64}", f["official_source_url_sha256"])
            assert f["parsed_text_status"] in {
                "OCRLESS_TEXT_SEPARATELY_REVIEWED_PDFTOTEXT_NATIONAL_REGIME_JUSTIFICATION",
                "FILE_BYTES_VERIFIED_AFTER_RETRY_TEXT_NOT_PARSED",
                "DOCX_OR_XLSX_TEXT_EXTRACTED",
            }
            assert not any("http" in x["excerpt"].lower() for x in f["sampled_evidence"])
    a = EIS["procedures"][0]["original_files"][0]
    assert a["original_name"] == "НМЦК.xlsx"
    assert a["sha256"] == "3652c01b1e19e7dd340298c4b51466d541776387fbb53c6dca81a533ced20189"
    assert a["separately_retrieved_verified"] is True


def test_workspace_live_public_card_proven_not_pro_or_bid_authorization():
    assert WS["schema_version"] == "b2b-priority-workspace-card-19041-v1"
    assert WS["tender_id"] == "workspace-19041"
    assert WS["http_status"] == 200
    assert WS["organizer_type"] == "Юридическое лицо"
    assert WS["platform_status"] == "Идет прием заявок"
    assert WS["published_deadline"] == "2026-10-31"
    assert WS["published_deadline_hour"] == "UNKNOWN"
    assert WS["application_pro_access_required"] == "UNVERIFIED"
    assert WS["company_three_year_portfolio_verified"] is False
    assert WS["same_customer_as_workspace_19042"] == "UNVERIFIED"
    assert WS["bid_ready"] is False and WS["no_external_action"] is True
    assert datetime.fromisoformat(WS["retrieved_at_utc"]).tzinfo is not None
    assert re.fullmatch("[0-9a-f]{64}", WS["sha256"])
    assert "от 3 лет" in WS["source_backed_requirements"]["experience"]


def test_all_risks_reference_attested_original_source_files():
    assert DEC["schema_version"] == "b2b-priority-three-conservative-triage-20261017-v1"
    assert DEC["real_bid_go_count"] == 0 and DEC["owner_eligibility_approvals"] == 0
    assert DEC["new_workspace_or_stand_created"] is False
    assert DEC["original_getdocs_archival_status_only"] is True
    assert len(DEC["cases"]) == 3
    known = {c["procurement_number"]: c for c in EIS["procedures"]}
    for case in DEC["cases"]:
        assert case["bid_ready"] is False
        assert case["live_legal_status_verified"] is False
        assert case["participant_qualification_verified"] is False
        assert case["blocking_owner_checks"]
        if case["kind"] == "44FZ_ARCHIVED_OFFICIAL_ORIGINAL":
            original = known[case["id"]]
            source_names = {f["original_name"]: f for f in original["original_files"]}
            for ref in case["source_based_deliverables"]:
                source = source_names[ref["original_name"]]
                assert source["sha256"] == ref["sha256"]
                assert original["zip_sha256"] == ref["original_zip_sha256"]
                assert original["notice_xml_sha256"] == ref["notice_xml_sha256"]
                assert source["file_id"] == ref["file_id"]
    museum, yakutia, mobile = DEC["cases"]
    assert museum["nmck_rub"] == 1600000 and museum["contract_warranty_months"] == 12
    assert museum["contract_performance_security_percent_of_final_price"] == 5
    assert yakutia["nmck_rub"] == 4550000
    assert yakutia["hard_rights_dependency"] == "GeoPrime"
    assert yakutia["price_score_weight_percent"] == 30
    assert yakutia["qualification_score_weight_percent"] == 70
    assert yakutia["additional_warranty_security_rub"] == 227500
    assert mobile["minimum_commercial_mobile_experience_years"] == 3
    assert mobile["observed_original_html_sha256"] == WS["sha256"]
    assert mobile["public_deadline_hour"] == "UNKNOWN"
    assert "GEOPRIME" in yakutia["preliminary_priority"]
    assert "PORTFOLIO" in mobile["preliminary_priority"]


def test_report_no_unsupported_owner_go_or_elided_rights():
    report = (ROOT / "B2B_PRIORITY_THREE_FULL_TZ_2026-10-17.md").read_text()
    assert "НЕ" in report or "не GO" in report
    assert "GeoPrime" in report
    assert "227 500" in report
    assert "30% цена / 70% квалификация" in report
    assert "Electron 20" in report
    assert "от 3 лет" in report
    assert "Три кейса пока не BID_READY" in report
