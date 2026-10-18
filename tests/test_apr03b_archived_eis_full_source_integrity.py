"""The only saved Operator Workspace: original source bytes vs fresh EIS read-only receipts."""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ops import verify_eis_archive_sources as cli
from src.modules.tender_operator_agent_demo.eis_archived_source_integrity import (
    SourceIntegrityError,
    fetch_current_getdocs_and_binaries,
    verified_saved_observation,
    verify_saved_source_snapshot,
)

RUN = "toa-run-20261017120000-a1b2c3"
NUMBER = "0372200172326000015"
NOTICE = f"epNotificationEZK2020_{NUMBER}_1_01A11A810BFD7EBAB3819B3AE3BE0014.xml"
FIRST_URL = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=one"
SECOND_URL = "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid=two"
SOURCES = {"contract.doc": (FIRST_URL, b"contract-original-1"),
           "task.docx": (SECOND_URL, b"task-original-2")}
XML = (
    "<export><epNotificationEZK2020><commonInfo><purchaseNumber>"
    + NUMBER + "</purchaseNumber><versionNumber>1</versionNumber>"
    "<purchaseObjectInfo>Museum site</purchaseObjectInfo><endDT>2026-10-16T10:00:00+03:00</endDT>"
    "<maxPrice>1000000.00</maxPrice><attachments>"
    + "".join(f"<attachmentInfo><fileName>{name}</fileName><url>{url}</url></attachmentInfo>"
              for name, (url, _) in SOURCES.items())
    + "</attachments></commonInfo></epNotificationEZK2020></export>"
).encode()


@pytest.fixture
def case(tmp_path: Path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv("AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR", str(root))
    directory = root / RUN
    original = directory / "input"
    extracted = original / "extracted"
    extracted.mkdir(parents=True)
    (directory / "procurement").mkdir()
    with zipfile.ZipFile(original / "documentation-archive.zip", "w") as archive:
        archive.writestr(NOTICE, XML)
    (extracted / "original.xml").write_bytes(XML)
    from src.modules.tender_operator_agent_demo.eis_official_procedure import (
        classify_official_eis_archive,
    )

    classified = classify_official_eis_archive(original / "documentation-archive.zip", NUMBER)
    assert classified["status"] == "ATTESTED_COMPETITIVE"
    items = [
        {"file_id": "FILE-01", "original_name": NOTICE, "stored_name": "extracted/original.xml",
         "extension": ".xml", "size_bytes": len(XML), "source_type": "eis_getdocs_archive"},
    ]
    for index, (name, (url, data)) in enumerate(SOURCES.items(), 2):
        stored = f"original-{index}.bin"
        (original / stored).write_bytes(data)
        items.append({
            "file_id": f"FILE-{index:02d}", "original_name": name,
            "stored_name": stored, "size_bytes": len(data),
            "source_type": "notice_xml_attachments", "source_url": url,
        })
    metadata = {
        "run_id": RUN, "procurement_id": NUMBER, "reestr_number": NUMBER,
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "archive_stored_name": "documentation-archive.zip",
        "original_getdocs_archive_sha256": classified["archive_sha256"],
        "official_eis_procedure": classified,
        "notice_revision_selected": {"purchase_number": NUMBER, "version": 1,
                                      "file_id": "FILE-01",
                                      "current_live_eis_verified": False},
        "files": items,
        "human_in_the_loop": True, "external_actions": False,
    }
    (directory / "metadata.json").write_text(json.dumps(metadata))
    return directory, metadata


class FakeEIS:
    settings = SimpleNamespace(user_agent="test-audit", timeout_seconds=4)

    def __init__(self, case, *, wrong_archive=False, wrong_binary=False):
        self.case = case
        self.wrong_archive = wrong_archive
        self.wrong_binary = wrong_binary
        self.calls = []

    def get_docs_by_reestr_number(self, number):
        assert number == NUMBER
        self.calls.append("getdocs")
        return SimpleNamespace(status="completed", archive_urls=["https://int.zakupki.gov.ru/file.zip"],
                               archive_url=None)

    def download_archive(self, url, dest):
        assert url == "https://int.zakupki.gov.ru/file.zip"
        data = (self.case / "input/documentation-archive.zip").read_bytes()
        if self.wrong_archive:
            data += b"x"
        (dest / "documentation-archive.zip").write_bytes(data)
        self.calls.append("getdocs_download")
        return SimpleNamespace(stored_name="documentation-archive.zip")

    def _http_get(self, url, *, headers, timeout, max_bytes):
        assert headers["User-Agent"] == self.settings.user_agent
        assert timeout <= 30
        self.calls.append("filestore")
        name = next((k for k, (u, _) in SOURCES.items() if u == url), None)
        assert name is not None
        data = SOURCES[name][1]
        if self.wrong_binary and name == "contract.doc":
            data = b"replacement-original"
        assert max_bytes == len(SOURCES[name][1])
        return data, "application/download"


def test_offline_audit_exact_xml_urls_bytes_and_no_eis_claim(case):
    root, _ = case
    baseline = (root / "metadata.json").read_bytes()
    result = verify_saved_source_snapshot(RUN)
    assert result["published_links"] == 2
    assert result["saved_url_and_bytes_verified"] == 2
    assert len(result["files"]) == 2
    assert result["archived_notice_version"] == 1
    assert result["current_live_notice_status_verified"] is False
    assert result["owner_legal_go"] is False
    assert "uid=one" not in json.dumps(result)
    assert (root / "metadata.json").read_bytes() == baseline
    assert verified_saved_observation(RUN) is None


def test_fresh_getdocs_and_two_filestore_binary_sha_and_safe_receipt(case):
    root, _ = case
    client = FakeEIS(root)
    data = fetch_current_getdocs_and_binaries(
        RUN, client=client, observed_at=datetime(2026, 10, 17, 9, 20, tzinfo=UTC)
    )
    assert data["fresh_getdocs_original_zip_matches"] is True
    assert data["fresh_official_filestore_bytes_match"] == 2
    assert data["current_live_notice_status_verified"] is False
    assert data["owner_legal_go"] is False
    assert client.calls == ["getdocs", "getdocs_download", "filestore", "filestore"]
    assert cli.save_receipt(RUN, data)
    assert not cli.save_receipt(RUN, data)
    projected = verified_saved_observation(RUN)
    assert projected["official_binary_match_count"] == 2
    assert projected["verified_at_utc"] == "2026-10-17T09:20:00+00:00"
    assert projected["current_live_notice_status_verified"] is False
    assert projected["owner_legal_go"] is False


@pytest.mark.parametrize("case_change", [
    "wrong_bytes", "wrong_url", "wrong_name", "missing_file", "extra_file",
    "missing_zip", "changed_zip", "malicious_path", "falsified_zip_hash",
    "claim_live_status"
])
def test_offline_source_mismatch_fails_closed(case, case_change):
    root, m = case
    path = root / "metadata.json"
    if case_change == "wrong_bytes":
        (root / "input/original-2.bin").write_bytes(b"forged!!")
    elif case_change == "wrong_url":
        m["files"][1]["source_url"] += "&x=stale"
    elif case_change == "wrong_name":
        m["files"][1]["original_name"] = "unrelated.doc"
    elif case_change == "missing_file":
        (root / "input/original-2.bin").unlink()
    elif case_change == "extra_file":
        m["files"].append({**m["files"][1], "file_id": "FILE-04"})
    elif case_change == "missing_zip":
        (root / "input/documentation-archive.zip").unlink()
    elif case_change == "changed_zip":
        with zipfile.ZipFile(root / "input/documentation-archive.zip", "a") as z:
            z.writestr("extra.bin", b"tamper")
    elif case_change == "malicious_path":
        m["files"][1]["stored_name"] = "../outside"
    elif case_change == "falsified_zip_hash":
        m["official_eis_procedure"]["archive_sha256"] = "0" * 64
    elif case_change == "claim_live_status":
        m["notice_revision_selected"]["current_live_eis_verified"] = True
    path.write_text(json.dumps(m))
    with pytest.raises((SourceIntegrityError, ValueError)):
        verify_saved_source_snapshot(RUN)


@pytest.mark.parametrize("bad", ["fresh_zip_changed", "fresh_attachment_changed"])
def test_live_source_change_not_promoted_to_verified(case, bad):
    root, _ = case
    client = FakeEIS(root, wrong_archive=bad == "fresh_zip_changed",
                     wrong_binary=bad == "fresh_attachment_changed")
    with pytest.raises(SourceIntegrityError):
        fetch_current_getdocs_and_binaries(RUN, client=client)
    assert verified_saved_observation(RUN) is None


def test_receipt_invalidated_when_saved_binary_changes(case):
    root, _ = case
    observation = fetch_current_getdocs_and_binaries(RUN, client=FakeEIS(root))
    assert cli.save_receipt(RUN, observation)
    assert verified_saved_observation(RUN) is not None
    (root / "input/original-2.bin").write_bytes(b"damaged-original")
    assert verified_saved_observation(RUN) is None


def test_forged_current_status_and_extra_file_block_projection(case):
    root, _ = case
    observation = fetch_current_getdocs_and_binaries(RUN, client=FakeEIS(root))
    assert cli.save_receipt(RUN, observation)
    output = root / "procurement/archived_eis_source_integrity_receipt.json"
    forged = json.loads(output.read_text())
    forged["current_live_notice_status_verified"] = True
    output.write_text(json.dumps(forged))
    assert verified_saved_observation(RUN) is None
    with pytest.raises(ValueError):
        cli.save_receipt(RUN, forged)


@pytest.mark.parametrize("bad_timestamp", [
    "2099-01-01T00:00:00+00:00",
    "2026-10-17T09:20:00",
    "not-a-timestamp",
    "2026-10-17T09:20:00+00:00" + "x" * 200,
])
def test_untrusted_observation_clock_cannot_claim_verified_freshness(case, bad_timestamp):
    root, _ = case
    original = fetch_current_getdocs_and_binaries(
        RUN, client=FakeEIS(root),
        observed_at=datetime(2026, 10, 17, 9, 20, tzinfo=UTC),
    )
    assert cli.save_receipt(RUN, original)
    receipt_path = root / "procurement/archived_eis_source_integrity_receipt.json"
    forged = json.loads(receipt_path.read_text())
    forged["fresh_observation_utc"] = bad_timestamp
    receipt_path.write_text(json.dumps(forged))
    assert verified_saved_observation(RUN) is None



@pytest.mark.parametrize("bad_timestamp", [
    "2099-01-01T00:00:00+00:00",
    "2026-10-17T09:20:00",
    "unparseable"
])
def test_untrusted_timestamp_cannot_be_persisted_as_official_retrieval(case, bad_timestamp):
    root, _ = case
    original = fetch_current_getdocs_and_binaries(
        RUN, client=FakeEIS(root),
        observed_at=datetime(2026, 10, 17, 9, 20, tzinfo=UTC),
    )
    original["fresh_observation_utc"] = bad_timestamp
    with pytest.raises(ValueError, match="retrieval observation time"):
        cli.save_receipt(RUN, original)
    assert not (root / "procurement/archived_eis_source_integrity_receipt.json").exists()
