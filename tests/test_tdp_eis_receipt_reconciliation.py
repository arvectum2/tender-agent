import hashlib

from src.modules.tender_operator_agent_demo.eis_receipt_reconciliation import (
    reconcile_receipts,
)

UID = "01A10C59B0B8791B8D464C4C14D10A94"
URI = f"https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={UID}"
B = b"genuine source bytes"
H = hashlib.sha256(B).hexdigest()
RECEIPT = {"files": [{"uid": UID, "url": URI, "sha256": H}]}
DP = [
    {
        "canonical_uri": URI,
        "content_hash": H,
        "documents": [{"document_id": "doc1", "content_hash": H}],
        "metadata": {"notice_revision": "rev1"},
    }
]


def test_no_export_is_not_accepted():
    result = reconcile_receipts(RECEIPT, {UID: B}, [])
    assert result.status == "UNKNOWN" and "NO_DP_SOURCE_MATCH" in result.error_codes


def test_missing_independent_revision_is_unknown_even_when_bytes_match():
    result = reconcile_receipts(RECEIPT, {UID: B}, DP)
    assert (
        result.status == "UNKNOWN"
        and "NOTICE_REVISION_NOT_INDEPENDENTLY_VERIFIED" in result.error_codes
    )


def test_falsified_source_bytes_are_rejected():
    result = reconcile_receipts(
        RECEIPT, {UID: b"tampered"}, DP, independently_verified_notice_revision="rev1"
    )
    assert (
        result.status == "UNKNOWN" and "RECEIPT_BINARY_MISMATCH" in result.error_codes
    )


def test_correct_revision_only_matches_source_bytes_not_chunks():
    result = reconcile_receipts(
        RECEIPT, {UID: B}, DP, independently_verified_notice_revision="rev1"
    )
    assert (
        result.status == "SOURCE_BYTES_MATCHED_CHUNKS_UNVERIFIED"
        and result.matched_originals == 1
    )


def test_wrong_revision_is_unknown():
    result = reconcile_receipts(
        RECEIPT, {UID: B}, DP, independently_verified_notice_revision="rev2"
    )
    assert (
        result.status == "UNKNOWN"
        and "DP_NOTICE_REVISION_MISMATCH" in result.error_codes
    )


def test_wrong_uri_rejected():
    bad = {
        "files": [
            {**RECEIPT["files"][0], "url": "https://evil.example/file?uid=" + UID}
        ]
    }
    result = reconcile_receipts(
        bad, {UID: B}, DP, independently_verified_notice_revision="rev1"
    )
    assert result.status == "UNKNOWN" and "UNTRUSTED_SOURCE_URI" in result.error_codes


def test_empty_receipts_unknown():
    assert reconcile_receipts({}, {}, []).error_codes == ("MISSING_RECEIPTS",)


def test_duplicate_filereceipt_never_passes():
    double = {"files": RECEIPT["files"] * 2}
    assert (
        "DUPLICATE_SOURCE_UID"
        in reconcile_receipts(
            double, {UID: B}, DP, independently_verified_notice_revision="rev1"
        ).error_codes
    )


def test_bad_dp_metadata_never_raises_and_remains_unknown():
    broken = [{**DP[0], "metadata": None, "documents": None}]
    result = reconcile_receipts(
        RECEIPT, {UID: B}, broken, independently_verified_notice_revision="rev1"
    )
    assert result.status == "UNKNOWN"


def test_noncanonical_filestore_path_rejected():
    wrong = {
        "files": [{**RECEIPT["files"][0], "url": URI.replace("/priz/", "/other/")}]
    }
    assert "UNTRUSTED_SOURCE_URI" in reconcile_receipts(wrong, {UID: B}, DP).error_codes


def test_malformed_export_not_a_success():
    assert reconcile_receipts(RECEIPT, {UID: B}, None).status == "UNKNOWN"
