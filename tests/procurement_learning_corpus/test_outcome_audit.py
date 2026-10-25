"""Historical outcome evidence audit stays read-only and avoids fabricated gold."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.procurement_llm.audit_outcomes import (
    AKSAY,
    EXPECTED,
    KALUGA,
    audit_outcomes,
)


def _fixtures(root: Path) -> tuple[Path, Path, Path]:
    s = root / "aksay.json"
    s.write_text(json.dumps({"summary": {
        "procurement_number": AKSAY, "applications_total": 55,
        "applications_admitted": 45, "our_price_rub": 119000,
        "our_rank": 38, "winner_price_rub": 28400,
        "our_status": "admitted",
    }, "bids": []}))
    xml = b"""<root><applicationInfo><appNumber>193</appNumber>
    <admissionResultsInfo><admissionResultInfo><admitted>true</admitted>
    </admissionResultInfo></admissionResultsInfo>
    <finalPrice>449000.00</finalPrice><appRating>26</appRating>
    </applicationInfo></root>"""
    z = root / "original.zip"
    with ZipFile(z, "w") as archive:
        archive.writestr(f"epProtocolEZK2020Final_{KALUGA}_1_SAVED.xml", xml)
    items = []
    for event_id, ref in EXPECTED.items():
        items.append({
            "event_id": event_id, "procurement_ref": ref,
            "email_message_ids": ["gmail-source-id"], "owner_identity_verified_by_etp_email": True,
            "raw_emails_copied": False, "training_label_approved": False, "legal_gold": False,
        })
    for event in items:
        if event["event_id"].endswith("withdrawal-v1"):
            event.update({"application_number": None, "participation": "unknown"})
        if event["event_id"].endswith("app193-admitted-v1"):
            event.update({
                "application_number": "193",
                "original_eis_zip_sha256": sha256(z.read_bytes()).hexdigest(),
                "original_eis_xml_sha256": sha256(xml).hexdigest(),
            })
    p = root / "operator.json"
    p.write_text(json.dumps({"schema": "manual-candidate-import-v1", "items": items}))
    return s, z, p


def _audit(f):
    a, b, c = f
    return audit_outcomes(
        aksay_statistics=a, kaluga_archive=b, operator_batch=c
    )


def test_exact_sources_do_not_promote_human_gold_or_aksay_rank(tmp_path):
    summary = _audit(_fixtures(tmp_path))
    assert summary["operator_metadata_events_verified"] == 8
    assert summary["kaluga"]["application_number"] == "193"
    assert summary["kaluga"]["final_price_rub"] == 449000
    assert summary["kaluga"]["withdrawal_attributed_to_app206"] is False
    assert summary["aksay"]["archived_snapshot_status"].startswith("derived")
    assert summary["aksay"]["our_derived_rank"] == 38
    assert summary["aksioma"]["our_bid_rank_proven_by_original_protocol"] is False
    assert summary["museum"]["official_outcome_available_in_audit"] is False
    assert summary["new_postgres_records"] == summary["approved_training_labels"] == 0
    assert summary["mutations"] == 0
    assert "gmail-source-id" not in json.dumps(summary)
    assert str(tmp_path) not in json.dumps(summary)


def test_unknown_withdrawal_must_remain_unattributed(tmp_path):
    f = _fixtures(tmp_path)
    b = json.loads(f[2].read_text())
    for event in b["items"]:
        if event["event_id"].endswith("withdrawal-v1"):
            event["application_number"] = "206"
    f[2].write_text(json.dumps(b))
    with pytest.raises(ValueError, match="Withdrawal"):
        _audit(f)


def test_swapped_eis_zip_sha_cannot_be_mislabeled(tmp_path):
    f = _fixtures(tmp_path)
    batch = json.loads(f[2].read_text())
    for item in batch["items"]:
        if item["event_id"].endswith("app193-admitted-v1"):
            item["original_eis_zip_sha256"] = "a" * 64
    f[2].write_text(json.dumps(batch))
    with pytest.raises(ValueError, match="ZIP SHA"):
        _audit(f)


def test_stale_derived_aksay_price_fails_closed(tmp_path):
    f = _fixtures(tmp_path)
    summary = json.loads(f[0].read_text())
    summary["summary"]["our_price_rub"] = 120000
    f[0].write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="derived Aksay"):
        _audit(f)


def test_missing_or_extra_operator_event_rejected(tmp_path):
    f = _fixtures(tmp_path)
    source = json.loads(f[2].read_text())
    source["items"] = source["items"][:-1]
    f[2].write_text(json.dumps(source))
    with pytest.raises(ValueError, match="ETP event"):
        _audit(f)


def test_raw_chat_or_untrusted_gold_rejected(tmp_path):
    f = _fixtures(tmp_path)
    source = json.loads(f[2].read_text())
    source["items"][0]["legal_gold"] = True
    f[2].write_text(json.dumps(source))
    with pytest.raises(ValueError, match="provenance/source-scope"):
        _audit(f)


def test_symlinked_private_batch_rejected(tmp_path):
    f = _fixtures(tmp_path)
    link = tmp_path / "linked-batch.json"
    link.symlink_to(f[2])
    with pytest.raises(ValueError, match="symlinked"):
        audit_outcomes(aksay_statistics=f[0], kaluga_archive=f[1], operator_batch=link)
