"""31 observation path: public first-party receipts -> canonical unreviewed metadata.

Does not touch production PostgreSQL, a network endpoint, or model training.
"""
from __future__ import annotations

import copy
import hashlib
import json
import stat
from pathlib import Path

import pytest

from scripts.procurement_llm import build_research_intake as b
from scripts.procurement_llm.import_candidates import _manual_payload_items
from src.modules.procurement_learning_corpus.service import validate_candidate

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/roadmap"


def _data():
    return (
        b._read(b.EIS_FILE),
        b._read(b.B2B_SIX_FILE),
        b._read(b.B2B_ONE_FILE),
    )


def _workspace():
    rows = []
    for id_ in range(19000, 19021):
        number = str(id_)
        rows.append({
            "id": "workspace-" + number,
            "source_url": "https://workspace.ru/tenders/sample-" + number + "/",
            "source_http_status": 200,
            "source_html_sha256": hashlib.sha256(number.encode()).hexdigest(),
            "observed_at_utc": "2026-10-18T16:00:00+00:00",
            "source_gate": "PUBLIC_CORPORATE_CANDIDATE_ONLY",
            "platform_status": "Идет прием заявок",
            "public_corporate_candidate": True,
            "authenticated_legal_entity_bidder_verified": False,
            "commercial_go": False,
            "external_actions_taken": False,
        })
    return ({
        "contract_version": "b2b_workspace_firstparty_public_originals_v1",
        "firstparty_http200_cards_parsed": 21,
        "strict_owner_qualified_bid_opportunities": 0,
        "items": rows,
    }, hashlib.sha256(b"fixed workspace receipt test bytes").hexdigest())


def _all(workspace=None):
    eis, six, one = _data()
    return b.build(workspace=workspace, eis=eis, b2b_six=six, b2b_one=one)


def test_real_git_attestations_replay_ten_source_events_without_workspace():
    output = _all()
    assert output["total"] == 10
    assert output["stats"] == {"workspace": 0, "eis": 3, "b2bcenter": 7}
    assert output["batch"]["schema"] == "manual-candidate-import-v1"
    ids = {i["event_id"] for i in output["batch"]["items"]}
    assert len(ids) == 10
    for event in output["batch"]["items"]:
        assert event["participation"] == "reviewed_only"
        assert event["review_state"] == "source_documented"
        assert event["source_role"] == "development_exposed"
        assert event["training_labels"] == "NOT_REVIEWED"
        assert event["owner_bid_go"] is False
        assert event["company_bid_eligibility_verified"] is False
        assert event["current_legal_stage_verified"] is False
        assert event["human_verified_interpretation"] is False
        assert event["source_payload_is_only_metadata"] is True
        assert event["raw_document_bytes_copied"] is False
        assert not event.get("signed_human_gold")
    for candidate in _manual_payload_items(output["batch"]):
        validate_candidate(candidate)
        assert candidate["candidate_split"] == "manual_candidate_not_blind"
        assert candidate["training_status"] == "candidate_unreviewed"
        assert candidate["visibility_scope"] == "owner_internal"
        assert candidate["customer_id"] is None


def test_synthetic_21_workspace_source_attestations_plus_ten_real_replay_as_31():
    receipt = _workspace()
    saved = copy.deepcopy(receipt)
    out = _all(workspace=receipt)
    assert receipt == saved
    assert out["total"] == 31
    assert out["stats"] == {"workspace": 21, "eis": 3, "b2bcenter": 7}
    assert len({e["procurement_ref"] for e in out["batch"]["items"]}) == 31
    assert len({e["event_id"] for e in out["batch"]["items"]}) == 31
    assert out == _all(workspace=receipt)


def test_original_receipt_replay_idempotent_and_sha_update_append_only():
    receipt = _workspace()
    before = _all(workspace=receipt)
    again = _all(workspace=receipt)
    assert before["batch"] == again["batch"]
    newer = copy.deepcopy(receipt)
    newer[0]["items"][0]["source_html_sha256"] = "a" * 64
    latest = _all(workspace=newer)
    assert before["batch"]["items"][0]["event_id"] != latest["batch"]["items"][0]["event_id"]
    assert before["batch"]["items"][1]["event_id"] == latest["batch"]["items"][1]["event_id"]


def test_changed_receipt_even_same_html_creates_new_observation():
    before = _all(workspace=_workspace())
    new = list(_workspace())
    new[1] = "b" * 64
    after = _all(workspace=tuple(new))
    assert before["batch"]["items"][0]["event_id"] != after["batch"]["items"][0]["event_id"]


@pytest.mark.parametrize("source_url", [
    "https://evil.invalid/tenders/sample-19000/",
    "http://workspace.ru/tenders/sample-19000/",
    "https://workspace.ru/tenders/sample-19000/?auth=token",
    "https://workspace.ru/tenders/sample-19001/",
    "https://user:pass@workspace.ru/tenders/sample-19000/",
])
def test_workspace_wrong_origin_query_or_identity_refused(source_url):
    receipt = _workspace()
    receipt[0]["items"][0]["source_url"] = source_url
    with pytest.raises(b.ResearchIntakeError):
        _all(workspace=receipt)


@pytest.mark.parametrize("mutator", [
    lambda x: x[0]["items"][0].update({"commercial_go": True}),
    lambda x: x[0]["items"][0].update({"authenticated_legal_entity_bidder_verified": True}),
    lambda x: x[0]["items"][0].update({"source_html_sha256": "broken"}),
    lambda x: x[0]["items"][0].update({"source_gate": "BID_GO"}),
    lambda x: x[0]["items"][0].update({"observed_at_utc": "2026-10-18T16:00:00"}),
])
def test_workspace_false_positive_security_claim_rejected(mutator):
    item = _workspace()
    mutator(item)
    with pytest.raises(b.ResearchIntakeError):
        _all(workspace=item)


def test_source_duplicate_procurement_numbers_refused():
    receipt = _workspace()
    receipt[0]["items"][1] = copy.deepcopy(receipt[0]["items"][0])
    with pytest.raises(b.ResearchIntakeError):
        _all(workspace=receipt)


def test_archived_notice_promotion_not_allowed():
    e, six, one = _data()
    data = copy.deepcopy(e)
    data[0]["records"][0]["current_live_legal_status_verified"] = True
    with pytest.raises(b.ResearchIntakeError):
        b.build(workspace=None, eis=data, b2b_six=six, b2b_one=one)


def test_firstparty_b2b_rfi_never_bid_or_training_gold():
    output = _all()["batch"]["items"]
    item = next(i for i in output if i["procurement_ref"] == "b2bcenter:4632891")
    assert item["source_gate"] == "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD"
    assert item["owner_bid_go"] is False
    assert item["training_labels"] == "NOT_REVIEWED"
    suspect = next(i for i in output if i["procurement_ref"] == "b2bcenter:4632699")
    assert suspect["source_gate"] == "SOURCE_IDENTITY_OR_STAGE_REQUIRES_REVIEW"
    assert suspect["source_identity_parse_state"] == "UNVERIFIED_FAIL_CLOSED"


def test_b2b_wrong_original_url_rejected():
    eis, six, one = _data()
    six = copy.deepcopy(six)
    six[0]["items"][0]["exact_original_card_url"] += "?token=private"
    with pytest.raises(b.ResearchIntakeError):
        b.build(workspace=None, eis=eis, b2b_six=six, b2b_one=one)


def test_b2b_false_bid_permission_rejected():
    eis, six, one = _data()
    six = copy.deepcopy(six)
    six[0]["items"][0]["owner_bid_go"] = True
    with pytest.raises(b.ResearchIntakeError):
        b.build(workspace=None, eis=eis, b2b_six=six, b2b_one=one)


def test_path_symlink_or_oversized_receipt_rejected(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"some": "data"}))
    assert b._read(good)[0]["some"] == "data"
    indirect = tmp_path / "link.json"
    indirect.symlink_to(good)
    with pytest.raises(b.ResearchIntakeError):
        b._read(indirect)
    huge = tmp_path / "huge.json"
    huge.write_bytes(b" " * (b.MAX_RECEIPT + 100))
    with pytest.raises(b.ResearchIntakeError):
        b._read(huge)


def test_duplicate_json_keys_rejected(tmp_path):
    f = tmp_path / "dup.json"
    f.write_text('{"a":1,"a":2}')
    with pytest.raises(b.ResearchIntakeError, match="duplicate"):
        b._read(f)


def test_private_output_only_in_existing_restricted_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "PRIVATE_ROOT", tmp_path)
    name = tmp_path / "review.json"
    batch = json.dumps(_all()["batch"], ensure_ascii=False, indent=2) + "\n"
    b._private_write(name, batch)
    assert name.read_text() == batch
    assert stat.S_IMODE(name.stat().st_mode) == 0o600
    b._private_write(name, batch)
    with pytest.raises(b.ResearchIntakeError, match="immutable"):
        b._private_write(name, batch + " ")
    with pytest.raises(b.ResearchIntakeError):
        b._private_write(tmp_path.parent / "outside.json", batch)
    link = tmp_path / "linked.json"
    link.symlink_to(name)
    with pytest.raises(b.ResearchIntakeError):
        b._private_write(link, batch)


def test_metadata_stays_well_below_existing_importer_payload_cap():
    for event in _all(workspace=_workspace())["batch"]["items"]:
        assert len(json.dumps(event).encode()) < 4096
        assert "password" not in event and "signed_human_gold" not in event
