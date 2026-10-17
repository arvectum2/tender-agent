"""Offline replay: later recovery receipts must be SHA-pinned and exact original identities."""
from __future__ import annotations

import csv
import hashlib
import io
import json

import pytest

from src.modules.tender_operator_agent_demo.r4_filestore_recovery_overlay import (
    attach_later_original_binary_receipts,
)


def fixtures() -> tuple[dict, str, bytes, bytes, str, str]:
    registry = "0372200172326000015"
    original = {
        "reg_number": registry,
        "official_archive_status": "HISTORIC_ARCHIVED_ZIP",
        "attached_non_xml_files": 1,
        "blockers": ["OFFICIAL_ATTACHMENT_BINARY_RETRANSFER_NOT_CONFIRMED_IN_THIS_AUDIT",
                     "HUMAN_R4_REVIEW_NOT_SIGNED", "LIVE_EIS_STATUS_UNATTESTED"],
    }
    cases = [original] + [
        {"reg_number":f"{i:019d}","attached_non_xml_files":0,
         "blockers":["HUMAN_R4_REVIEW_NOT_SIGNED"]}
        for i in range(1,20)
    ]
    historic = {
        "cases": cases, "source_matrix_sha256":"a"*64,
        "summary":{"non_xml_attached_binary_count":1},
    }
    rows = [{
        "reg_number":registry,"file_id":"FILE-04","extension":".docx",
        "historic_SHA256":"b"*64,"file_size_bytes":"42",
        "cached_bytes_SHA_match":"YES","attachment_UID_in_official_XML":"YES",
    }]
    out = io.StringIO()
    writer=csv.DictWriter(out,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    source = {"files":[{
        "reg_number":registry,"file_id":"FILE-04",
        "stored_sha256":"b"*64,"stored_bytes":42,
        "official_file_uid":"c"*32,"uid_in_official_archive_xml":True,
    }]}
    verified={"results":[{
        "uid":"c"*32,"reg_number":registry,
        "result":"verified","sha256_equal":True,"size_equal":True,
        "source_binary_verified":True,"actual_bytes":42,
    }]}
    source_bytes=json.dumps(source,sort_keys=True).encode()
    verified_bytes=json.dumps(verified,sort_keys=True).encode()
    return historic,out.getvalue(),source_bytes,verified_bytes,hashlib.sha256(source_bytes).hexdigest(),hashlib.sha256(verified_bytes).hexdigest()


def test_attested_later_recovery_updates_archival_gap_not_current_legal_gate():
    matrix,files,source,receipt,sha_source,sha_recheck=fixtures()
    result=attach_later_original_binary_receipts(
        matrix,files,source,receipt,expected_source_sha256=sha_source,
        expected_recheck_sha256=sha_recheck,required=1,
    )
    first=result["cases"][0]
    assert result["later_recovery"]["verified_original_binaries"]==1
    assert result["later_recovery"]["verified_original_binary_bytes"]==42
    assert first["later_20261012_verified_official_binary_recovery"]==1
    assert "OFFICIAL_ATTACHMENT_BINARY_RETRANSFER_NOT_CONFIRMED_IN_THIS_AUDIT" not in first["blockers"]
    assert "RECOVERED_BINARY_CURRENT_NOTICE_REVISION_UNATTESTED" in first["blockers"]
    assert first["human_source_review"]=="NOT_VERIFIED"
    assert first["bid_ready"] is False
    assert first["latest_official_notice_attested"] is False
    assert result["human_gold_attested"] is False
    assert result["bid_ready"] is False
    serialized=json.dumps(result)
    assert "official_file_uid" not in serialized
    assert "uid_in_official_archive_xml" not in serialized
    assert result==attach_later_original_binary_receipts(
        matrix,files,source,receipt,expected_source_sha256=sha_source,
        expected_recheck_sha256=sha_recheck,required=1,
    )


def test_pinned_original_manifest_rejects_mutation_even_if_declared_success():
    matrix,files,source,receipt,sha_source,sha_recheck=fixtures()
    with pytest.raises(ValueError,match="pinned archived receipt"):
        attach_later_original_binary_receipts(
            matrix,files,source+b" ",receipt,
            expected_source_sha256=sha_source,expected_recheck_sha256=sha_recheck,
            required=1,
        )


def test_private_original_and_public_file_sha_mismatch_fails_closed():
    matrix,files,source,receipt,_,sha_recheck=fixtures()
    changed=json.loads(source)
    changed["files"][0]["stored_sha256"]="e"*64
    source_changed=json.dumps(changed,sort_keys=True).encode()
    with pytest.raises(ValueError,match="SHA/size"):
        attach_later_original_binary_receipts(
            matrix,files,source_changed,receipt,
            expected_source_sha256=hashlib.sha256(source_changed).hexdigest(),
            expected_recheck_sha256=sha_recheck,required=1,
        )


def test_private_receipt_claiming_verified_but_wrong_bytes_fails_closed():
    matrix,files,source,receipt,sha_source,_=fixtures()
    tampered=json.loads(receipt)
    tampered["results"][0]["actual_bytes"]=43
    altered=json.dumps(tampered,sort_keys=True).encode()
    with pytest.raises(ValueError,match="mismatched_retrieved_binary"):
        attach_later_original_binary_receipts(
            matrix,files,source,altered,
            expected_source_sha256=sha_source,
            expected_recheck_sha256=hashlib.sha256(altered).hexdigest(),required=1,
        )


def test_historical_official_recovery_never_fills_unknown_live_status():
    matrix,files,source,receipt,s,r=fixtures()
    result=attach_later_original_binary_receipts(
        matrix,files,source,receipt,
        expected_source_sha256=s,expected_recheck_sha256=r,required=1,
    )
    for entry in result["cases"]:
        assert entry["arv001_release_ready"] is False
        assert entry["human_source_review"] == "NOT_VERIFIED"
        assert entry["latest_official_notice_attested"] is False
        assert entry["expert_gold"] is False
