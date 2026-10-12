"""Never mix obsolete source attachments from earlier official EIS notice ZIP editions."""
from pathlib import Path

from src.modules.tender_operator_agent_demo import procurement_intake_service as service
from src.modules.tender_operator_agent_demo.eis_notice_revision_selector import (
    select_latest_archived_notice_files,
)

NUMBER = "0360600005326000018"
OTHER_NUMBER = "0372200172326000015"
UID1 = "A" * 32
UID2 = "B" * 32
UID3 = "C" * 32


def notice(version: int, uid: str = UID1, number: str = NUMBER) -> dict:
    return {
        "original_name": f"epNotificationEF2020_{number}_{version}_{uid}.xml",
        "stored_name": f"source-{version}-{uid[:3]}.xml",
        "role_hint": "notice",
    }


def test_old_notice_revision_removed_but_clarification_preserved():
    clarification = {
        "original_name": f"epClarificationDoc_{NUMBER}_null_{UID3}.xml",
        "stored_name": "clarification.xml",
    }
    files = [notice(1, UID1), clarification, notice(2, UID2)]
    result = select_latest_archived_notice_files(
        files, expected_registry_number=NUMBER
    )
    assert result == [clarification, files[2]]


def test_all_legacy_notice_without_version_preserved():
    legacy = {"original_name": "old-notice.xml", "role_hint": "notice"}
    assert select_latest_archived_notice_files(
        [legacy], expected_registry_number=NUMBER
    ) == [legacy]


def test_unversioned_notice_dropped_if_versioned_notice_exists():
    unknown = {"original_name": "epNotificationArchive.xml"}
    current = notice(3, UID2)
    assert select_latest_archived_notice_files(
        [unknown, current], expected_registry_number=NUMBER
    ) == [current]


def test_foreign_procurement_notice_excluded_by_expected_registry_number():
    own = notice(1, UID1)
    foreign = notice(3, UID2, OTHER_NUMBER)
    assert select_latest_archived_notice_files(
        [foreign, own], expected_registry_number=NUMBER
    ) == [own]


def test_unbound_mixed_procurement_notice_fails_closed():
    own = notice(1, UID1)
    foreign = notice(3, UID2, OTHER_NUMBER)
    assert select_latest_archived_notice_files(
        [foreign, own], expected_registry_number=None
    ) == []


def test_ambiguous_same_revision_different_uids_fails_closed():
    assert select_latest_archived_notice_files(
        [notice(2, UID1), notice(2, UID2)],
        expected_registry_number=NUMBER,
    ) == []


def test_same_latest_uid_deduplicated():
    original = notice(2, UID2)
    again = {**original, "stored_name": "duplicate.xml"}
    assert select_latest_archived_notice_files(
        [notice(1, UID1), original, again],
        expected_registry_number=NUMBER,
    ) == [original]


def test_real_attachment_discovery_uses_only_latest_archived_notice(monkeypatch, tmp_path: Path):
    old = notice(1, UID1)
    new = notice(2, UID2)

    def document(uid: str) -> str:
        return (
            "<root><attachmentsInfo><attachmentInfo>"
            "<fileName>Техническое задание.docx</fileName>"
            "<url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html"
            f"?uid={uid}</url>"
            "</attachmentInfo></attachmentsInfo></root>"
        )

    for entry, uid in ((old, UID1), (new, UID2)):
        (tmp_path / entry["stored_name"]).write_text(document(uid), encoding="utf-8")
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _run_id: tmp_path)
    found = service._discover_notice_xml_attachments(
        "isolated-run",
        {"notice_number": NUMBER, "files": [old, new]},
    )
    assert len(found) == 1
    assert found[0].name == "Техническое задание.docx"
    assert found[0].url is not None and f"uid={UID2}" in found[0].url
    assert UID1 not in found[0].url


def test_procurement_id_binds_notice_identity_when_notice_number_absent(monkeypatch, tmp_path: Path):
    """A foreign newer notice cannot suppress the intended procurement attachment."""
    own = notice(1, UID1)
    foreign = notice(9, UID2, OTHER_NUMBER)
    xml_template = (
        "<root><attachmentsInfo><attachmentInfo>"
        "<fileName>Техническое задание.docx</fileName>"
        "<url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html"
        "?uid={uid}</url>"
        "</attachmentInfo></attachmentsInfo></root>"
    )
    for row, uid in ((own, UID1), (foreign, UID2)):
        (tmp_path / row["stored_name"]).write_text(
            xml_template.format(uid=uid), encoding="utf-8"
        )
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _run_id: tmp_path)
    result = service._discover_notice_xml_attachments(
        "real-number-run",
        {"procurement_id": NUMBER, "files": [foreign, own]},
    )
    assert len(result) == 1
    assert result[0].url is not None and UID1 in result[0].url
    assert UID2 not in result[0].url
