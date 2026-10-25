"""Adversarial R4 archival-source cohort quality tests; no real blind sources."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from scripts.quality.apr067_r4_development_cohort import (
    _EXACT,
    _NORMALIZED,
    _UNSUPPORTED,
    CohortEvidenceError,
    check_original_zip,
    digest,
    evaluate,
    quote_breakdown,
)

METHOD = "COMPETITIVE_ELECTRONIC_AUCTION"
SHA = "a" * 64


def quotes():
    old = [
        {"checks": [{"status": _EXACT} for _ in range(22)]
         + [{"status": _NORMALIZED} for _ in range(3)]
         + [{"status": _UNSUPPORTED}]}
    ]
    new = [
        {
            "registry_number": "0372200172326000015",
            "quote_literal": i != 20,
            "quote_length_valid": i < 18,
            "claim_format_count_valid": i < 18,
            "original_binary_sha256": SHA, "original_text_sha256": SHA,
        }
        for i in range(21)
    ]
    return {
        "saved_model_claims": {
            "claims": 26, "cases": old,
            "literal_official_originals": 22,
            "whitespace_variant_official_originals": 3,
            "unsubstantiated_literal_quotes": 1,
        },
        "additional_four_cases_and_21_original_binaries": {
            "claim_checks": new, "model_claims_checked": 21,
            "model_claims_exact_source_quotes": 20,
            "claims_requiring_quote_correction": 1,
            "claims_breaching_quote_length_policy": 3,
            "model_batches_exceeding_claim_count_cap": 3,
        },
        "all_saved_model_claims_checked": 47,
    }


@pytest.fixture
def cohort(tmp_path: Path):
    source = tmp_path / "actual-private-historical-development"
    source.mkdir()
    cases, notices = [], []
    for i in range(20):
        number = f"{3700000000000000000 + i:019d}"
        role = "NEW_OFFICIAL_POSITIVE_REPLACEMENT" if i >= 16 else "ORIGINAL_20_CORPUS"
        base = (source / "ai-expert-20261012/positive-eis-replacements-20261012"
                if role.startswith("NEW_") else source / "independent-20261012")
        case_dir = base / number
        case_dir.mkdir(parents=True)
        notice = (
            "<export><purchaseNumber>" + number + "</purchaseNumber>"
            "<purchaseNumber>0026</purchaseNumber><attachmentInfo>"
            "<fileName>source-doc.docx</fileName></attachmentInfo></export>"
        ).encode()
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("selected-notice.xml", notice)
        blob = mem.getvalue()
        (case_dir / "documentation-archive.zip").write_bytes(blob)
        entry = {
            "registry_number": number, "source_role": role,
            "archived_zip_sha256": digest(blob),
            "selected_xml_sha256": digest(notice),
            "selected_xml_attachment_references": 1,
            "archived_version": 1, "competitive_method": METHOD,
            "notice_type": "epNotificationEF2020",
        }
        cases.append(entry)
        notices.append({
            "registry_number": number, "original_zip_sha256": entry["archived_zip_sha256"],
            "original_xml_sha256": entry["selected_xml_sha256"],
            "archived_version": 1, "method": METHOD, "bid_ready": False,
        })
    manifest = {
        "schema_version": "apr067-r4-historic-development-source-v1",
        "scope": "R4_20_HISTORICAL_DEVELOPMENT_COMPETITIVE_44FZ_ONLY",
        "official_current_edition_asserted": False,
        "legal_gold_signed": False, "bid_ready": False,
        "source_selection_sha256": "b" * 64,
        "r4_audit_sha256": "c" * 64,
        "cases": cases,
    }
    audit = {
        **quotes(),
        "competitive_notices": notices,
        "negative_controls": [{"bid_ready": False} for _ in range(4)],
        "source_cohort": {"competitive": 20, "negative": 4},
        "official_source_verified": 21,
        "selected_original_notice_attachment_coverage": {
            "notice_attachment_references": 20,
            "source_shas_attested": 20,
            "case_count": 20,
            "evidence_methods": {"OLDER_VERIFIED_TLS_RECHECK": 20},
        },
        "selected_original_notice_text_availability": {
            "attachments_with_nonempty_source_text": 20,
            "text_extraction_completeness_asserted": False,
        },
        "historical_model_report_deadline_audit": {
            "saved_reports_verified": 10,
            "date_conflict_count": 2,
            "unattested_strong_blocker_decisions": 8,
        },
    }
    return source, manifest, audit


def check(cohort):
    source, manifest, audit = cohort
    return evaluate(
        manifest=manifest, audit=audit, source_root=source,
        private_selection_sha256="b" * 64,
        public_audit_sha256="c" * 64,
        regenerated_audit_sha256="c" * 64,
    )


def test_twenty_archived_originals_and_47_quote_breakdown(cohort):
    result = check(cohort)
    assert result["sample_cases"] == 20
    assert result["metrics"]["zip_sha_matched"]["num"] == 20
    assert result["metrics"]["registry_matching_selected_XML_sha_matched"]["num"] == 20
    quote = result["r4_saved_quote_evidence"]
    assert (quote["exact_literal"], quote["layout_only_difference"], quote["unsupported_literal"]) == (42, 3, 2)
    assert round(quote["exact_quote_rate"]["value"] * 100, 2) == 89.36
    assert result["metrics"]["operator_full_e2e_completion_rate"]["value"] is None
    assert result["metrics"]["independent_human_gold"]["state"] == "NOT_MEASURED"
    assert result["legal_gold_signed"] is False and result["bid_ready"] is False


def test_archived_zip_byte_tamper_detected(cohort):
    root, manifest, _ = cohort
    row = manifest["cases"][0]
    file = root / "independent-20261012" / row["registry_number"] / "documentation-archive.zip"
    file.write_bytes(file.read_bytes() + b"MALFORMED")
    with pytest.raises(CohortEvidenceError, match="ZIP SHA256 differs"):
        check(cohort)


def test_original_xml_digest_swapped_detected(cohort):
    _, manifest, _ = cohort
    manifest["cases"][1]["selected_xml_sha256"] = SHA
    with pytest.raises(CohortEvidenceError, match="not unique/unchanged"):
        check(cohort)


def test_source_revision_or_wrong_registry_rejected(cohort):
    _, manifest, _ = cohort
    manifest["cases"][0]["registry_number"] = "0000000000000000001"
    with pytest.raises(CohortEvidenceError):
        check(cohort)


@pytest.mark.parametrize("change", ["current", "legal", "ready", "duplicate", "source_selection", "audit_digest"])
def test_forged_provenance_or_legal_permission_blocked(cohort, change):
    source, manifest, audit = cohort
    if change == "current":
        manifest["official_current_edition_asserted"] = True
    elif change == "legal":
        manifest["legal_gold_signed"] = True
    elif change == "ready":
        audit["negative_controls"][0]["bid_ready"] = True
    elif change == "duplicate":
        manifest["cases"][1]["registry_number"] = manifest["cases"][0]["registry_number"]
    elif change == "source_selection":
        manifest["source_selection_sha256"] = SHA
    else:
        manifest["r4_audit_sha256"] = SHA
    with pytest.raises(CohortEvidenceError):
        evaluate(
            manifest=manifest, audit=audit, source_root=source,
            private_selection_sha256="b" * 64,
            public_audit_sha256="c" * 64,
            regenerated_audit_sha256="c" * 64,
        )


@pytest.mark.parametrize("key", ["claims", "literal_official_originals", "whitespace_variant_official_originals", "unsubstantiated_literal_quotes"])
def test_fabricated_old_quote_totals_blocked(key):
    audit = quotes()
    audit["saved_model_claims"][key] += 1
    with pytest.raises(CohortEvidenceError, match="quote totals"):
        quote_breakdown(audit)


def test_tampered_new_quote_and_claim_limit_inference_blocked():
    audit = quotes()
    audit["additional_four_cases_and_21_original_binaries"]["claim_checks"][0]["quote_literal"] = False
    with pytest.raises(CohortEvidenceError):
        quote_breakdown(audit)


def test_forged_attachment_coverage_denominator_rejected(cohort):
    cohort[2]["selected_original_notice_attachment_coverage"]["source_shas_attested"] = 99
    with pytest.raises(CohortEvidenceError, match="attachment coverage"):
        check(cohort)


def test_empty_or_invalid_source_role_rejected(cohort):
    root, manifest, _ = cohort
    for role in ("", "BLIND_EVALUATION_CASE", "../independent-20261012"):
        with pytest.raises(CohortEvidenceError, match="role"):
            check_original_zip(source_root=root, entry={**manifest["cases"][0], "source_role": role})


def test_stored_xml_attachment_revision_wrong_denominator_rejected(cohort):
    root, manifest, _ = cohort
    with pytest.raises(CohortEvidenceError, match="attachment count"):
        check_original_zip(
            source_root=root,
            entry={**manifest["cases"][0], "selected_xml_attachment_references": 2},
        )


def test_source_zip_symlink_outside_root_rejected(cohort, tmp_path):
    root, manifest, _ = cohort
    row = manifest["cases"][0]
    target = root / "independent-20261012" / row["registry_number"] / "documentation-archive.zip"
    target.unlink()
    out = tmp_path / "outside.zip"
    out.write_bytes(b"NOT A ZIP")
    target.symlink_to(out)
    with pytest.raises(CohortEvidenceError, match="ZIP unavailable"):
        check(cohort)
