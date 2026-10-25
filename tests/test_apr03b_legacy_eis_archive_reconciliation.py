"""Owner-controlled legacy getDocsIP saved ZIP binding; source hash and latest gate."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.ops import reconcile_legacy_getdocs_archive as reconcile
from src.modules.tender_operator_agent_demo import (
    operator_workspace_evidence as evidence,
)

NUMBER = "0372200172326000015"
RUN = "toa-run-20261012123456-abcdef"
ZIP_NAME = "documentation-archive.zip"
XML_NAME = f"epNotificationEZK2020_{NUMBER}_1_01A11A810BFD7EBAB3819B3AE3BE0014.xml"
XML = (
    "<export><epNotificationEZK2020><commonInfo>"
    f"<purchaseNumber>{NUMBER}</purchaseNumber>"
    "<versionNumber>1</versionNumber>"
    "<publishDTInEIS>2026-10-12T10:00:00+03:00</publishDTInEIS>"
    "<purchaseObjectInfo>Разработка сайта музея</purchaseObjectInfo>"
    "<endDT>2026-10-16T10:00:00+03:00</endDT>"
    "<maxPrice>1000000.00</maxPrice></commonInfo>"
    "</epNotificationEZK2020></export>"
).encode()


@pytest.fixture
def saved(tmp_path: Path, monkeypatch):
    root = tmp_path / "operator-runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))
    directory = root / RUN
    source = directory / "input"
    extracted = source / "extracted"
    extracted.mkdir(parents=True)
    with zipfile.ZipFile(source / ZIP_NAME, "w") as archive:
        archive.writestr(XML_NAME, XML)
    (extracted / "notice.xml").write_bytes(XML)
    metadata = {
        "run_id": RUN, "procurement_id": NUMBER, "reestr_number": NUMBER,
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "archive_downloaded": True,
        "getdocs_status": "completed",
        "archive_source_host": "int.zakupki.gov.ru",
        "getdocs_ref_id": "ref-001", "getdocs_request_id": "req-001",
        "files": [{
            "file_id": "FILE-01", "original_name": XML_NAME,
            "display_name": XML_NAME, "stored_name": "extracted/notice.xml",
            "extension": ".xml", "size_bytes": len(XML),
        }],
        "archive_stored_name": None,
        "original_getdocs_archive_sha256": None,
        "official_eis_procedure": None,
        "notice_revision_selected": None,
        "human_in_the_loop": True,
        "external_actions": False,
    }
    (directory / "metadata.json").write_text(json.dumps(metadata))
    (directory / "events.jsonl").write_text("\n".join([
        json.dumps({"event_type": "eis_getdocs_started", "timestamp": "2026-10-12T10:00:00Z",
                    "details": {"reestr_number": NUMBER, "soap_method": "getDocsByReestrNumber"}}),
        json.dumps({"event_type": "eis_archive_url_received", "timestamp": "2026-10-12T10:00:01Z",
                    "details": {"archive_source_host": "int.zakupki.gov.ru", "archive_url_present": True}}),
        json.dumps({"event_type": "eis_archive_downloaded", "timestamp": "2026-10-12T10:00:01Z",
                    "details": {"stored_name": ZIP_NAME, "size_bytes": (source / ZIP_NAME).stat().st_size}}),
    ]) + "\n")
    return directory


def test_readonly_dry_run_attests_saved_archive_but_never_live_source(saved):
    before = (saved / "metadata.json").read_bytes()
    result, receipt = reconcile.evaluate(RUN)
    assert (saved / "metadata.json").read_bytes() == before
    assert receipt["archive_sha256"] == hashlib.sha256((saved / "input" / ZIP_NAME).read_bytes()).hexdigest()
    assert receipt["archived_notice_version"] == 1
    assert receipt["selected_file_id"] == "FILE-01"
    assert not receipt["live_eis_verified"] and not receipt["business_go_eligible"]
    assert result["official_eis_procedure"]["status"] == "ATTESTED_COMPETITIVE"
    assert result["notice_revision_requires_review"] is True
    assert result["notice_revision_selected"]["current_live_eis_verified"] is False
    assert result["archived_zip_reconciliation"]["not_original_transport_time_sha_receipt"] is True


def test_apply_exact_hashes_once_and_evidence_pins_single_notice(saved):
    before = (saved / "metadata.json").read_bytes()
    events = (saved / "events.jsonl").read_text().splitlines()
    new, receipt = reconcile.evaluate(RUN)
    assert reconcile.apply(
        RUN, new, receipt,
        expected_archive_sha256=receipt["archive_sha256"],
        expected_metadata_sha256=hashlib.sha256(before).hexdigest(),
    )
    packet = evidence.get_operator_source_evidence(RUN)
    assert packet["source_selection"] == "pinned_latest_archived_notice_revision"
    assert packet["facts"]["procurement_title"]["status"] == "KNOWN"
    assert "НЕ подтверждены" in " ".join(packet["warnings"])
    assert not packet["external_action_allowed"]
    assert len((saved / "events.jsonl").read_text().splitlines()) == len(events) + 1
    after, r2 = reconcile.evaluate(RUN)
    assert r2["already_reconciled"]
    assert not reconcile.apply(
        RUN, after, r2,
        expected_archive_sha256=r2["archive_sha256"],
        expected_metadata_sha256=r2["metadata_sha256_before"],
    )
    assert len((saved / "events.jsonl").read_text().splitlines()) == len(events) + 1


@pytest.mark.parametrize("mode", [
    "changed_saved_xml", "wrong_receipt_size", "conflicting_preexisting_hash",
    "unsafe_archive_name", "changed_current_source", "bad_expected_sha",
])
def test_never_backfill_unsupported_source_provenance(saved, mode):
    meta_path = saved / "metadata.json"
    old_bytes = meta_path.read_bytes()
    if mode == "changed_saved_xml":
        (saved / "input/extracted/notice.xml").write_bytes(XML.replace(b"1000000", b"9000000"))
    elif mode == "wrong_receipt_size":
        p = saved / "events.jsonl"
        records = [json.loads(line) for line in p.read_text().splitlines()]
        records[2]["details"]["size_bytes"] = 100
        p.write_text("\n".join(map(json.dumps, records)))
    elif mode == "conflicting_preexisting_hash":
        obj = json.loads(old_bytes)
        obj["original_getdocs_archive_sha256"] = "0" * 64
        meta_path.write_text(json.dumps(obj))
        old_bytes = meta_path.read_bytes()
    elif mode == "changed_current_source":
        new, receipt = reconcile.evaluate(RUN)
        obj = json.loads(old_bytes)
        obj["external_actions"] = True
        meta_path.write_text(json.dumps(obj))
        with pytest.raises(reconcile.ProvenanceError, match="source file or metadata changed since preflight"):
            reconcile.apply(RUN, new, receipt, expected_archive_sha256=receipt["archive_sha256"],
                            expected_metadata_sha256=receipt["metadata_sha256_before"])
        return
    elif mode == "bad_expected_sha":
        new, receipt = reconcile.evaluate(RUN)
        with pytest.raises(reconcile.ProvenanceError, match="hash changed"):
            reconcile.apply(RUN, new, receipt, expected_archive_sha256="0" * 64,
                            expected_metadata_sha256=receipt["metadata_sha256_before"])
        return
    with pytest.raises(reconcile.ProvenanceError):
        reconcile.evaluate(RUN, archive_name="../outside.zip" if mode == "unsafe_archive_name" else ZIP_NAME)
    assert meta_path.read_bytes() == old_bytes


def test_rejects_archive_falsely_matching_different_notice(saved):
    archive = saved / "input" / ZIP_NAME
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(XML_NAME, XML.replace(NUMBER.encode(), b"0372200172326000016"))
    with pytest.raises(reconcile.ProvenanceError):
        reconcile.evaluate(RUN)
