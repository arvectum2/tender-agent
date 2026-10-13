"""Offline XML source binding for 44-FZ special procedure getDocsIP guards."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo.eis_official_procedure import (
    classify_official_eis_archive,
)

NUMBER = "0349500000226000003"


def make_zip(
    path: Path, *, number: str = NUMBER, kind: str = "epNotificationEZT2020",
    inside_number: str | None = None, versions: tuple[int, ...] = (1,),
    xml_override: bytes | None = None,
) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for ver in versions:
            body = xml_override or (
                f"<export><{kind}><commonInfo><purchaseNumber>"
                f"{inside_number or number}</purchaseNumber></commonInfo>"
                f"</{kind}></export>"
            ).encode()
            z.writestr(f"{kind}_{number}_{ver}_01A0B2C3.xml", body)
    return path


def test_real_ezt_notice_type_attested_but_not_bid_approved(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip")
    result = classify_official_eis_archive(archive, NUMBER)
    assert result["status"] == "ATTESTED_SPECIAL"
    assert result["procedure_kind"] == "SINGLE_SUPPLIER_ART93_12"
    assert result["notice_type"] == "epNotificationEZT2020"
    assert result["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert result["source_purchase_number"] == NUMBER
    assert result["business_go_eligible"] is False
    assert result["current_live_eis_verified"] is False


@pytest.mark.parametrize("kind", ["epNotificationEF2020", "epNotificationEZK2020", "epNotificationEOK2020"])
def test_three_real_competitive_types_allow_normal_analysis(kind: str, tmp_path: Path):
    r = classify_official_eis_archive(make_zip(tmp_path / "eis.zip", kind=kind), NUMBER)
    assert r["status"] == "ATTESTED_COMPETITIVE"
    assert r["procedure_kind"] == "COMPETITIVE_44FZ"
    assert not r["business_go_eligible"]


def test_newest_revision_selected_and_all_versions_bound(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip", versions=(1, 2, 3))
    result = classify_official_eis_archive(archive, NUMBER)
    assert result["source_version"] == 3


def test_mismatched_filename_number_fails_closed(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip", number="0372200172326000015")
    assert classify_official_eis_archive(archive, NUMBER)["status"] == "CONFLICT"


def test_xml_purchase_number_mismatch_fails_closed(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip", inside_number="0372200172326000015")
    r = classify_official_eis_archive(archive, NUMBER)
    assert r["status"] == "CONFLICT"
    assert r["reason"] == "OFFICIAL_NOTICE_PURCHASE_NUMBER_CONFLICT"


def test_xml_type_forgery_conflict(tmp_path: Path):
    xml = (
        f"<export><epNotificationEZK2020><purchaseNumber>{NUMBER}</purchaseNumber>"
        "</epNotificationEZK2020></export>"
    ).encode()
    archive = make_zip(tmp_path / "eis.zip", xml_override=xml)
    assert classify_official_eis_archive(archive, NUMBER)["status"] == "CONFLICT"


def test_mixed_types_not_mistaken_for_competitive(tmp_path: Path):
    path = make_zip(tmp_path / "eis.zip", kind="epNotificationEF2020")
    with zipfile.ZipFile(path, "a") as z:
        z.writestr(
            f"epNotificationEZT2020_{NUMBER}_2_01A0B2C3.xml",
            f"<export><epNotificationEZT2020><purchaseNumber>{NUMBER}</purchaseNumber>"
            "</epNotificationEZT2020></export>",
        )
    assert classify_official_eis_archive(path, NUMBER)["status"] == "CONFLICT"


@pytest.mark.parametrize("kind", ["epNotificationUnexpected2020", "somethingElse"])
def test_unknown_document_type_not_promoted(kind: str, tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip", kind=kind)
    assert classify_official_eis_archive(archive, NUMBER)["status"] == "UNKNOWN"


def test_invalid_xml_and_missing_archive_do_not_produce_attestation(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip", xml_override=b"<export><wrong")
    assert classify_official_eis_archive(archive, NUMBER)["status"] == "UNKNOWN"
    assert classify_official_eis_archive(tmp_path / "missing.zip", NUMBER)["status"] == "UNKNOWN"
    assert classify_official_eis_archive(archive, "invalid")["status"] == "CONFLICT"


def test_malicious_symlink_not_read(tmp_path: Path):
    actual = make_zip(tmp_path / "real.zip")
    link = tmp_path / "linked.zip"
    link.symlink_to(actual)
    assert classify_official_eis_archive(link, NUMBER)["status"] == "UNKNOWN"


def test_archive_member_limit_blocks_success(tmp_path: Path):
    archive = make_zip(tmp_path / "eis.zip")
    with zipfile.ZipFile(archive, "a") as z:
        for n in range(251):
            z.writestr(f"x{n}.txt", "a")
    assert classify_official_eis_archive(archive, NUMBER)["status"] == "UNKNOWN"


def test_special_procedure_blocks_ordinary_analysis(tmp_path: Path, monkeypatch):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    make_zip(tmp_path / "official.zip")
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": NUMBER,
        "archive_stored_name": "official.zip",
    })
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _: tmp_path)
    monkeypatch.setattr(
        service, "_apply_document_set_completeness",
        lambda _: pytest.fail("special procurement must be stopped before document analysis"),
    )
    monkeypatch.setattr(
        service, "analyze_uploaded_demo_run",
        lambda _: pytest.fail("special procurement must not execute normal bidding analysis"),
    )
    with pytest.raises(HTTPException) as exc:
        service.analyze_eis_archive_run("run123")
    assert exc.value.status_code == 409
    assert exc.value.detail["procedure_kind"] == "SINGLE_SUPPLIER_ART93_12"


@pytest.mark.parametrize("kind", ["epNotificationEF2020", "epNotificationEZK2020", "epNotificationEOK2020"])
def test_competitive_routing_survives(tmp_path: Path, monkeypatch, kind: str):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    make_zip(tmp_path / "official.zip", kind=kind)
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": NUMBER,
        "archive_stored_name": "official.zip",
    })
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _: tmp_path)
    monkeypatch.setattr(service, "_apply_document_set_completeness", lambda _: {"analysis_allowed": True})
    monkeypatch.setattr(service, "analyze_uploaded_demo_run", lambda _: "NORMAL_ANALYSIS_CALLED")
    assert service.analyze_eis_archive_run("run123") == "NORMAL_ANALYSIS_CALLED"


def test_unbound_run_and_unreadable_xml_block(tmp_path: Path, monkeypatch):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    make_zip(tmp_path / "official.zip", xml_override=b"broken")
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": NUMBER,
    })
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _: tmp_path)
    monkeypatch.setattr(
        service, "analyze_uploaded_demo_run",
        lambda _: pytest.fail("must not analyze unknown"),
    )
    with pytest.raises(HTTPException) as exc:
        service.analyze_eis_archive_run("run123")
    assert exc.value.status_code == 409
    assert exc.value.detail["procedure_kind"] == "UNKNOWN"


def test_attested_special_is_marked_needs_review_not_auto_analyzed(monkeypatch):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "status": "ready_to_analyze",
        "analysis_status": "not_started",
        "limitations": [],
        "official_eis_procedure": {
            "status": "ATTESTED_SPECIAL",
            "procedure_kind": "SINGLE_SUPPLIER_ART93_12",
            "notice_type": "epNotificationEZT2020",
        },
    }
    events = []
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(service, "save_demo_run_metadata", lambda _, x: metadata.update(x))
    monkeypatch.setattr(
        service, "append_demo_run_event", lambda *args: events.append(args),
    )
    service._apply_attested_special_procedure_status("run123")
    assert metadata["status"] == "needs_review"
    assert metadata["analysis_status"] == "special_single_supplier_requires_separate_workflow"
    assert len(metadata["limitations"]) == 1
    assert events[0][1] == "eis_special_procedure_review_required"
    service._apply_attested_special_procedure_status("run123")
    assert len(metadata["limitations"]) == 1


def test_unknown_source_cannot_be_mislabeled_as_special(monkeypatch):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "status": "ready_to_analyze",
        "official_eis_procedure": {"status": "UNKNOWN", "procedure_kind": "UNKNOWN"},
    }
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(
        service,
        "save_demo_run_metadata",
        lambda *args: pytest.fail("no false status change"),
    )
    service._apply_attested_special_procedure_status("run123")
    assert metadata["status"] == "ready_to_analyze"


def test_nested_service_purchase_number_does_not_override_common_info(tmp_path: Path):
    original = (
        f"<export><epNotificationEZK2020><commonInfo>"
        f"<purchaseNumber>{NUMBER}</purchaseNumber></commonInfo>"
        "<serviceSigns><purchaseNumber>0010</purchaseNumber></serviceSigns>"
        "</epNotificationEZK2020></export>"
    ).encode()
    archive = make_zip(
        tmp_path / "eis.zip", kind="epNotificationEZK2020", xml_override=original,
    )
    r = classify_official_eis_archive(archive, NUMBER)
    assert r["status"] == "ATTESTED_COMPETITIVE"


def test_missing_authoritative_common_info_does_not_attest(tmp_path: Path):
    original = (
        f"<export><epNotificationEF2020><serviceSigns>"
        f"<purchaseNumber>{NUMBER}</purchaseNumber>"
        "</serviceSigns></epNotificationEF2020></export>"
    ).encode()
    archive = make_zip(
        tmp_path / "eis.zip", kind="epNotificationEF2020", xml_override=original,
    )
    r = classify_official_eis_archive(archive, NUMBER)
    assert r["status"] == "CONFLICT"


def test_swapped_archived_sha_is_blocked_before_analysis(tmp_path: Path, monkeypatch):
    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as service,
    )

    make_zip(tmp_path / "official.zip", kind="epNotificationEZK2020")
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": NUMBER,
        "archive_stored_name": "official.zip",
        "official_eis_procedure": {
            "status": "ATTESTED_COMPETITIVE",
            "archive_sha256": "a" * 64,
        },
    }
    monkeypatch.setattr(service, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(service, "get_demo_run_input_dir", lambda _: tmp_path)
    monkeypatch.setattr(
        service,
        "analyze_uploaded_demo_run",
        lambda _: pytest.fail("forged source hash must block analysis"),
    )
    with pytest.raises(HTTPException) as exc:
        service.analyze_eis_archive_run("run123")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "OFFICIAL_EIS_ARCHIVE_HASH_CHANGED"
