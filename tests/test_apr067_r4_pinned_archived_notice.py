"""Multiple historic EIS notice versions select only a ZIP/SHA-pinned archived edition."""
from __future__ import annotations

import hashlib
import zipfile

import pytest

from src.modules.tender_operator_agent_demo import operator_workspace_evidence as source
from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)

NUMBER = "0162200011826003089"
UID = "A" * 32


@pytest.fixture
def archive(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    extracted = input_dir / "extracted"
    extracted.mkdir(parents=True)
    original = input_dir / "documentation-archive.zip"

    def notice(version: int):
        return (
            f"<export><epNotificationEF2020><commonInfo>"
            f"<purchaseNumber>{NUMBER}</purchaseNumber>"
            f"<purchaseObjectInfo>Предмет версии {version}</purchaseObjectInfo>"
            f"<endDT>2026-10-{version + 10:02d}T11:00:00+03:00</endDT>"
            f"<maxPrice>{100000 * version}.00</maxPrice>"
            f"</commonInfo></epNotificationEF2020></export>"
        ).encode()

    files = []
    with zipfile.ZipFile(original, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for i, version in enumerate((1, 4), 1):
            filename = f"epNotificationEF2020_{NUMBER}_{version}_{UID}.xml"
            raw = notice(version)
            z.writestr(filename, raw)
            (extracted / filename).write_bytes(raw)
            files.append({
                "file_id": f"FILE-{i:02d}",
                "original_name": filename, "display_name": filename,
                "stored_name": "extracted/" + filename, "extension": ".xml",
            })
        for i, document in enumerate(("epProtocolEF2020Final", "fcsPlacementResult"), len(files) + 1):
            filename = f"{document}_{NUMBER}_1_{UID}.xml"
            raw = (
                f"<export><{document}><commonInfo>"
                f"<purchaseNumber>{NUMBER}</purchaseNumber>"
                f"</commonInfo></{document}></export>"
            ).encode()
            z.writestr(filename, raw)
            (extracted / filename).write_bytes(raw)
            files.append({
                "file_id": f"FILE-{i:02d}",
                "original_name": filename, "display_name": filename,
                "stored_name": "extracted/" + filename, "extension": ".xml",
            })
    classified = classify_official_eis_archive(original, NUMBER)
    assert classified["status"] == "ATTESTED_COMPETITIVE"
    assert classified["source_version"] == 4
    meta = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "procurement_id": NUMBER, "archive_stored_name": "documentation-archive.zip",
        "official_eis_procedure": classified,
        "files": files, "notice_revision_requires_review": True,
    }
    monkeypatch.setattr(source, "get_demo_run_input_dir", lambda _id: input_dir)
    monkeypatch.setattr(source, "load_demo_run_metadata", lambda _id: meta)
    return input_dir, meta, original


def test_latest_archived_original_selected_while_live_status_unknown(archive):
    _directory, meta, _original = archive
    packet = source.get_operator_source_evidence("run")
    assert packet["source_candidate_count"] == 2
    assert packet["source_selection"] == "pinned_latest_archived_notice_revision"
    assert packet["facts"]["procurement_title"]["value"] == "Предмет версии 4"
    assert packet["facts"]["nmck"]["value"] == 400000.0
    assert all(v["status"] == "KNOWN" and len(v["evidence"]) == 1 for v in packet["facts"].values())
    assert "НЕ подтверждены" in packet["warnings"][0]
    assert meta["official_eis_procedure"]["current_live_eis_verified"] is False
    assert packet["human_control_required"] and not packet["external_action_allowed"]


def test_altered_saved_xml_refuses_even_if_metadata_claims_v4(archive):
    directory, _meta, _original = archive
    target = next((directory / "extracted").glob(f"epNotificationEF2020_{NUMBER}_4_*.xml"))
    target.write_bytes(target.read_bytes() + b"modified")
    r = source.get_operator_source_evidence("run")
    assert r["source_selection"] == "archived_notice_source_hash_mismatch"
    assert all(x["status"] == "UNKNOWN" for x in r["facts"].values())


@pytest.mark.parametrize("field", ["archive_sha256", "notice_xml_sha256", "source_version", "source_purchase_number", "notice_type"])
def test_forged_or_mismatched_original_receipt_fails_closed(archive, field):
    _dir, meta, _source = archive
    meta["official_eis_procedure"][field] = ("b" * 64 if "sha" in field else "forged")
    r = source.get_operator_source_evidence("run")
    assert r["source_selection"] == "archived_notice_source_hash_mismatch"
    assert all(x["status"] == "UNKNOWN" for x in r["facts"].values())


def test_no_archive_rejects_fake_live_source_provenance(archive):
    _dir, meta, original = archive
    original.unlink()
    meta["official_eis_procedure"]["current_live_eis_verified"] = True
    r = source.get_operator_source_evidence("run")
    assert r["source_selection"] == "archived_notice_source_hash_mismatch"


def test_two_latest_v4_members_are_ambiguous_even_if_archive_classifier_picks_one(archive):
    directory, meta, original = archive
    raw = next((directory / "extracted").glob(f"epNotificationEF2020_{NUMBER}_4_*.xml")).read_bytes()
    second = f"epNotificationEF2020_{NUMBER}_4_{'B' * 32}.xml"
    with zipfile.ZipFile(original, "a") as z:
        z.writestr(second, raw.replace(b"400000.00", b"499999.00"))
    meta["official_eis_procedure"] = classify_official_eis_archive(original, NUMBER)
    assert meta["official_eis_procedure"]["status"] == "ATTESTED_COMPETITIVE"
    r = source.get_operator_source_evidence("run")
    assert r["source_selection"] == "archived_notice_source_hash_mismatch"


def test_archive_symlink_fails_closed(archive, tmp_path):
    _directory, _meta, original = archive
    other = tmp_path / "other.zip"
    other.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(other)
    r = source.get_operator_source_evidence("run")
    assert r["source_selection"] == "archived_notice_source_hash_mismatch"


def test_quote_source_facts_bound_to_original_selected_hash(archive):
    directory, _meta, original = archive
    packet = source.get_operator_source_evidence("run")
    ref = packet["facts"]["procurement_title"]["evidence"][0]
    doc = directory / "extracted" / ref["document"]
    assert ref["source_ref"].startswith("eis-xml:")
    assert hashlib.sha256(doc.read_bytes()).hexdigest() == classify_official_eis_archive(
        original, NUMBER
    )["notice_xml_sha256"]


def test_pinned_archived_notice_html_cites_only_selected_v4(archive, tmp_path):
    _dir, meta, _source = archive
    from src.modules.tender_operator_agent_demo.operator_eis_report_citations import (
        append_official_eis_citations,
    )

    report = tmp_path / "report.html"
    report.write_text("<html><body><main><p>Архивная закупка</p></main></body></html>")
    inserted = append_official_eis_citations(
        report_path=report, run_id="run", metadata=meta,
    )
    actual = report.read_text()
    assert inserted == 3
    assert "Предмет версии 4" in actual
    assert "Предмет версии 1" not in actual
    assert "Это архивная редакция" in actual
    assert actual.count("eis-xml:") == 3


def test_forged_pinned_archive_cannot_create_html_evidence(archive, tmp_path):
    _dir, meta, _source = archive
    from src.modules.tender_operator_agent_demo.operator_eis_report_citations import (
        append_official_eis_citations,
    )

    meta["official_eis_procedure"]["notice_xml_sha256"] = "f" * 64
    report = tmp_path / "report.html"
    before = "<html><body><main>Исходный отчёт</main></body></html>"
    report.write_text(before)
    assert append_official_eis_citations(report_path=report, run_id="run", metadata=meta) == 0
    assert report.read_text() == before
