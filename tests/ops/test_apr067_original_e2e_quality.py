"""Independent negative cases for bounded APR06/07 source-quality observation."""
from __future__ import annotations

import copy
import hashlib
import html
from pathlib import Path

import pytest

from scripts.quality.apr067_original_e2e_quality import (
    EvidenceError,
    _original,
    inspect,
)

_NOTICE = "0372200172326000015"
_RUN = "toa-run-20261012200402-7249ed"
_VALUES = {
    "procurement_title": ("purchaseObjectInfo", "Разработка сайта"),
    "application_deadline": ("endDT", "2026-10-16T10:00:00+03:00"),
    "nmck": ("maxPrice", "1000000.00"),
}


@pytest.fixture
def case(tmp_path: Path):
    root = tmp_path / "private"
    saved = root / "qa-final-render" / "runs" / _RUN
    for folder in (root / "sources" / "input" / "extracted",
                   saved / "input" / "extracted", saved / "output"):
        folder.mkdir(parents=True)
    xml = (
        "<notice><purchaseNumber>" + _NOTICE + "</purchaseNumber>"
        + "".join(f"<{tag}>{html.escape(v)}</{tag}>" for tag, v in _VALUES.values())
        + "</notice>"
    ).encode("utf-8")
    source_file = "extracted/notice.xml"
    for folder in (root / "sources" / "input", saved / "input"):
        (folder / source_file).write_bytes(xml)
    sha = hashlib.sha256(xml).hexdigest()
    citations = "".join(
        f"<li><code>eis-xml:FILE-01:{tag}</code><p>notice.xml</p><blockquote>{html.escape(value)}</blockquote></li>"
        for tag, value in _VALUES.values()
    )
    report = (
        '<html><main><section id="official-eis-citations"><ul>'
        + citations + "</ul></section></main></html>"
    ).encode("utf-8")
    (saved / "output" / "report.html").write_bytes(report)
    (saved / "events.jsonl").write_text("".join(
        '{"event_type":"' + event + '"}\n'
        for event in ("eis_getdocs_started", "eis_archive_downloaded",
                      "run_created_from_eis_archive", "llm_analysis_completed")
    ))
    receipt = {
        "stage": "development_e2e",
        "reviewer_kind": "owner_delegated_chatgpt",
        "run_id": _RUN, "notice_number": _NOTICE,
        "report_sha256": hashlib.sha256(report).hexdigest(),
        "current_official_revision_verified": False,
        "official_originals": [{"original_name": "notice.xml", "sha256": sha, "verified_from_official": True}],
        "bid_submitted": False, "digital_signature_used": False, "payment_created": False,
        "production_mutated": False, "etp_mutated": False, "owner_legal_go_granted": False,
    }
    run = {
        "run_id": _RUN, "procurement_id": _NOTICE,
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "analysis_mode": "llm_tender_operator_provider",
        "ai_runtime_provenance": {
            "llm_invoked": True, "llm_calls_count": 4,
            "llm_provider": "openai_compatible", "llm_endpoint_host": "127.0.0.1",
            "fallback_reason": None,
        },
        "external_actions": False,
        "no_digital_signature": True, "no_email_sending": True, "no_platform_submission": True,
        "files": [{"file_id": "FILE-01", "display_name": "notice.xml",
                   "stored_name": source_file, "extension": ".xml",
                   "text_extraction_status": "extracted", "extracted_text_available": True}],
    }
    replay = {
        "analysis_http": 200, "persisted_llm_invoked": True,
        "persisted_analysis_mode": "llm_tender_operator_provider",
        "analysis_elapsed_seconds": 138.79,
        "extracted_original_count": 1, "failed_original_count": 0,
        **{key: 200 for key in (
            "authenticated_workspace", "history_http", "reopen_http",
            "read_only_registry_http", "report_json_http", "source_evidence_http")},
        **{key: 401 for key in ("unauth_workspace", "unauth_report", "unauth_evidence")},
        "pdf_export_http": 409, "docx_export_http": 409,
    }
    proof = {
        "run_id": _RUN, "registry_number": _NOTICE,
        "source_selection": "single_registry_matched_xml",
        "facts": {
            key: {"status": "KNOWN", "value": value, "evidence": [
                {"file_id": "FILE-01", "source_ref": f"eis-xml:FILE-01:{tag}",
                 "locator": f"XML:{tag}", "document": "notice.xml", "excerpt": value}
            ]}
            for key, (tag, value) in _VALUES.items()
        },
    }
    return root, receipt, run, replay, proof


def check(case):
    root, receipt, run, replay, proof = case
    return inspect(root=root, receipt=receipt, run=run, replay=replay, proof=proof)


def test_original_matched_source_metrics_have_bounded_denominators(case):
    verdict = check(case)
    assert verdict["status"] == "DEVELOPMENT_SOURCE_SUBSET_VERIFIED"
    assert verdict["metrics"]["selected_original_XML_citation_integrity"]["value"] == 1
    assert verdict["metrics"]["saved_source_sha_match"]["denominator"] == 1
    assert verdict["metrics"]["all_material_model_claim_accuracy"]["state"] == "NOT_MEASURED"
    assert verdict["metrics"]["human_gold_false_go"]["value"] is None
    assert verdict["commercial_acceptance"] == "NOT_MEASURED"
    assert verdict["model_promotion_authorized"] is False
    assert verdict["bid_or_payment_authorized"] is False


@pytest.mark.parametrize(("bucket", "field", "bad"), [
    ("receipt", "notice_number", "0372200172326000000"),
    ("receipt", "reviewer_kind", "independent_qualified_human"),
    ("receipt", "current_official_revision_verified", True),
    ("receipt", "bid_submitted", True),
    ("run", "analysis_mode", "fallback_deterministic_adapter"),
    ("run", "external_actions", True),
    ("replay", "persisted_llm_invoked", False),
    ("replay", "analysis_elapsed_seconds", False),
    ("replay", "extracted_original_count", 0),
    ("proof", "source_selection", "ambiguous_notice_revisions"),
])
def test_receipt_or_runtime_fabrication_fails_closed(case, bucket, field, bad):
    changed = copy.deepcopy(case)
    index = {"receipt": 1, "run": 2, "replay": 3, "proof": 4}[bucket]
    changed[index][field] = bad
    with pytest.raises(EvidenceError):
        check(changed)


def test_original_file_tampering_detected(case):
    root = case[0]
    doc = root / "qa-final-render" / "runs" / _RUN / "input" / "extracted" / "notice.xml"
    doc.write_bytes(doc.read_bytes().replace(b"1000000.00", b"9000000.00"))
    with pytest.raises(EvidenceError, match="source bytes tampered"):
        check(case)


def test_forged_excerpt_fails_even_if_model_report_contains_it(case):
    modified = copy.deepcopy(case)
    modified[4]["facts"]["nmck"]["evidence"][0]["excerpt"] = "9999999"
    with pytest.raises(EvidenceError, match="excerpt disagrees"):
        check(modified)


def test_report_citation_removed_fails_even_when_digest_updated(case):
    root, receipt, *_ = case
    output = root / "qa-final-render" / "runs" / _RUN / "output" / "report.html"
    text = output.read_text()
    text = text.replace("eis-xml:FILE-01:maxPrice", "not-backed-up")
    output.write_text(text)
    receipt["report_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(EvidenceError, match="HTML omits"):
        check(case)


def test_wrong_original_xml_notice_fails_with_all_digests_updated(case):
    root, receipt, run, replay, proof = case
    for f in (
        root / "sources" / "input" / "extracted" / "notice.xml",
        root / "qa-final-render" / "runs" / _RUN / "input" / "extracted" / "notice.xml",
    ):
        f.write_bytes(f.read_bytes().replace(_NOTICE.encode(), b"0372200172326000016"))
    receipt["official_originals"][0]["sha256"] = hashlib.sha256(
        (root / "sources" / "input" / "extracted" / "notice.xml").read_bytes()
    ).hexdigest()
    with pytest.raises(EvidenceError, match="wrong official XML"):
        inspect(root=root, receipt=receipt, run=run, replay=replay, proof=proof)


@pytest.mark.parametrize("name", ["../secret.xml", "/tmp/secret.xml", "a\\b.xml"])
def test_unsafe_source_file_path_rejected(case, name):
    folder = case[0] / "sources" / "input"
    with pytest.raises(EvidenceError, match="unsafe original"):
        _original(folder, name)


def test_symlink_to_external_file_rejected(case, tmp_path):
    folder = case[0] / "sources" / "input"
    (folder / "alias.xml").symlink_to(tmp_path / "elsewhere.xml")
    with pytest.raises(EvidenceError, match="unsafe original"):
        _original(folder, "alias.xml")



def test_non_local_model_provenance_disallowed(case):
    case[2]["ai_runtime_provenance"]["llm_endpoint_host"] = "remote-provider.example"
    with pytest.raises(EvidenceError, match="actual model invocation"):
        check(case)


def test_archival_export_success_is_unsafe(case):
    case[3]["pdf_export_http"] = 200
    with pytest.raises(EvidenceError, match="archival export"):
        check(case)


def test_missing_real_soap_download_event_disallowed(case):
    log = case[0] / "qa-final-render" / "runs" / _RUN / "events.jsonl"
    log.write_text('{"event_type":"llm_analysis_completed"}\n')
    with pytest.raises(EvidenceError, match="source acquisition"):
        check(case)


def test_citation_outside_official_panel_cannot_pass(case):
    root, receipt, *_ = case
    report = root / "qa-final-render" / "runs" / _RUN / "output" / "report.html"
    s = report.read_text()
    s = s.replace("eis-xml:FILE-01:maxPrice", "not-a-real-panel-citation")
    s += "eis-xml:FILE-01:maxPrice"  # fake quote outside the attributed evidence panel
    report.write_text(s)
    receipt["report_sha256"] = hashlib.sha256(report.read_bytes()).hexdigest()
    with pytest.raises(EvidenceError, match="HTML omits"):
        check(case)
