"""Prepare a private offline, source-pinned 44-FZ four-revision E2E staging run.

Runs the genuine archived EIS intake and its ZIP extractor, but substitutes
*only* the network getDocsIP/filestore calls with previously SHA-verified
archived original source bytes. Never use prospective or blind R4 material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

NUMBER = "0162200011826003089"
STAGE_NAME = "ta-apr067-r4-four-revisions-20261015"
RECEIPT_PIN = "df63a7619518ad9415ce81b7b27c964e8c81724d2f50fe497f428838dcbdecaf"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def resolve_original_eok_v3(
    *, source_root: Path, case: dict, pinned_case_manifest: Path,
) -> tuple[Path, list[dict]]:
    """Source-verify the original Oct-09 archive and frozen Oct-14 recovery.

    Unlike the positive replacement fixtures this case uses first-party
    saved-run originals and one independently recovered original ZIP. Every
    attachment is bound to the selected v3 XML by original EIS UID, exact
    filename, declared byte count, SHA, and first-party provenance.
    """
    if (case.get("registry_number") != "0348100024426000039"
            or case.get("source_role") != "ORIGINAL_20_CORPUS"
            or case.get("archived_version") != 3
            or case.get("notice_type") != "epNotificationEOK2020"
            or pinned_case_manifest.name !=
            "APR067_R4_SEVENTH_EOK_V3_SHA_PINNED_SOURCES_2026-10-15.json"):
        raise ValueError("unapproved original EOK source case")
    pinned = json.loads(pinned_case_manifest.read_text())
    if (pinned.get("registry_number") != case["registry_number"]
            or pinned.get("source_role") != case["source_role"]
            or pinned.get("selected_notice_version") != 3
            or pinned.get("selected_notice_type") != case["notice_type"]
            or pinned.get("archive_sha256") != case["archived_zip_sha256"]
            or pinned.get("selected_xml_sha256") != case["selected_xml_sha256"]
            or not isinstance(pinned.get("attachments"), list)
            or len(pinned["attachments"]) != case["selected_xml_attachment_references"]):
        raise ValueError("seventh frozen first-party manifest is inconsistent")
    def checked(relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ValueError("missing source relative path")
        path = source_root / relative
        if (path.is_symlink() or not path.resolve().is_relative_to(source_root)
                or not path.is_file()):
            raise ValueError("source escapes frozen original root")
        return path
    old_run = checked(pinned["original_saved_run"] + "/metadata.json").parent
    oldmeta = json.loads((old_run / "metadata.json").read_text())
    if oldmeta.get("procurement_id") != case["registry_number"]:
        raise ValueError("first-party saved-run procurement identity mismatch")
    archived = checked(pinned["archive_relative_path"])
    if sha(archived.read_bytes()) != case["archived_zip_sha256"]:
        raise ValueError("saved EIS ZIP original is not pinned")
    receipt_file = checked(pinned["recovery_receipt_relative_path"])
    if sha(receipt_file.read_bytes()) != pinned["recovery_receipt_sha256"]:
        raise ValueError("recovered filestore receipt changed")
    recovery = json.loads(receipt_file.read_text())
    seen: set[str] = set()
    rows = []
    for slot, row in enumerate(pinned["attachments"], start=1):
        uid = row.get("source_uid")
        if (not isinstance(uid, str) or not re.fullmatch(r"[0-9A-F]{32}", uid)
                or uid in seen or row.get("source_role") not in {
                    "oct09_first_party_saved_run",
                    "oct14_recovered_first_party_receipt",
                }):
            raise ValueError("invalid, repeated or unverified original UID")
        seen.add(uid)
        path = checked(row.get("source_root_relative_path"))
        if (path.suffix.lower() != row.get("file_extension")
                or path.stat().st_size != row.get("bytes")
                or sha(path.read_bytes()) != row.get("sha256")):
            raise ValueError("attached original sha/size/type mismatch")
        if row["source_role"] == "oct09_first_party_saved_run":
            matches = [
                x for x in oldmeta.get("files", [])
                if x.get("original_name") == row["official_name"]
                and x.get("size_bytes") == row["bytes"]
                and parse_qs(urlsplit(str(x.get("source_url") or "")).query).get("uid", [""])[0] == uid
                and (old_run / "input" / str(x.get("stored_name"))).resolve() == path.resolve()
            ]
            if len(matches) != 1:
                raise ValueError("old original saved-run source URL/UID/name/size not bound")
        else:
            matches = [
                x for x in recovery
                if x.get("registry_number") == case["registry_number"]
                and x.get("slot_in_original_notice") == slot
                and x.get("name_in_original_notice") == row["official_name"]
                and x.get("declared_bytes") == row["bytes"]
                and x.get("sha256") == row["sha256"]
                and x.get("notice_xml_sha256") == case["selected_xml_sha256"]
                and x.get("state") == "VERIFIED_FIRST_PARTY_BINARY"
                and (receipt_file.parent / case["registry_number"] / str(x.get("file"))).resolve() == path.resolve()
            ]
            if len(matches) != 1:
                raise ValueError("independent recovered original receipt mismatch")
        rows.append({
            "uid": uid, "file_extension": row["file_extension"],
            "actual_bytes": row["bytes"], "sha256": row["sha256"],
            "official_name": row["official_name"],
            "source_root_relative_path": row["source_root_relative_path"],
        })
    return archived, rows


def resolve_recovered_legacy_word_originals(
    *, source_root: Path, case: dict, pinned_case_manifest: Path,
) -> tuple[Path, list[dict]]:
    """Verify archived EF2020 cases with exact first-party Oct14 recovered files.

    Source UID/name/size is independently enforced by selected EIS XML in
    prepare(); this binder additionally verifies complete recovered SHA and
    original archive receipt, preserving legacy .doc and other originals.
    """
    approved = {
        "0127100008626000013": (1, "APR067_R4_EIGHTH_LEGACY_DOC_V1_SHA_PINNED_SOURCES_2026-10-15.json"),
        "0360600005326000018": (2, "APR067_R4_ORIGINAL_0360600005326000018_SHA_PINNED_SOURCES_2026-10-15.json"),
        "0895100000126000897": (1, "APR067_R4_ORIGINAL_0895100000126000897_SHA_PINNED_SOURCES_2026-10-15.json"),
    }
    expected = approved.get(case.get("registry_number"))
    if (expected is None or case.get("source_role") != "ORIGINAL_20_CORPUS"
            or case.get("notice_type") != "epNotificationEF2020"
            or case.get("archived_version") != expected[0]
            or pinned_case_manifest.name != expected[1]):
        raise ValueError("unapproved first-party recovered source case")
    pin = json.loads(pinned_case_manifest.read_text())
    if (pin.get("registry_number") != case["registry_number"]
            or pin.get("source_role") != "ORIGINAL_20_CORPUS"
            or pin.get("selected_notice_type") != case["notice_type"]
            or pin.get("selected_notice_version") != case["archived_version"]
            or pin.get("archive_sha256") != case["archived_zip_sha256"]
            or pin.get("selected_xml_sha256") != case["selected_xml_sha256"]
            or not isinstance(pin.get("attachments"), list)
            or len(pin["attachments"]) != case["selected_xml_attachment_references"]):
        raise ValueError("legacy original source manifest not bound")
    def checked(relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ValueError("missing original file path")
        path = source_root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(source_root) or not path.is_file():
            raise ValueError("unsafe historical first-party original path")
        return path

    meta_path = checked(pin["original_saved_run"] + "/metadata.json")
    if json.loads(meta_path.read_text()).get("procurement_id") != case["registry_number"]:
        raise ValueError("saved EIS archive procurement identity not attested")
    archive = checked(pin["archive_relative_path"])
    if sha(archive.read_bytes()) != case["archived_zip_sha256"]:
        raise ValueError("frozen EIS getDocsIP archive SHA mismatch")
    receipt_path = checked(pin["recovery_receipt_relative_path"])
    if sha(receipt_path.read_bytes()) != pin["recovery_receipt_sha256"]:
        raise ValueError("first-party recovery receipt SHA mismatch")
    receipt = json.loads(receipt_path.read_text())
    seen: set[str] = set()
    verified = []
    for item in pin["attachments"]:
        uid = item.get("source_uid")
        if (not isinstance(uid, str) or not re.fullmatch(r"[0-9A-F]{32}", uid)
                or uid in seen or item.get("source_role") != "oct14_recovered_first_party_receipt"):
            raise ValueError("unbound/duplicate original EIS UID")
        seen.add(uid)
        path = checked(item.get("source_root_relative_path"))
        if (path.stat().st_size != item.get("bytes")
                or path.suffix.lower() != item.get("file_extension")
                or sha(path.read_bytes()) != item.get("sha256")):
            raise ValueError("original legacy Word bytes or format differ")
        matched = [
            r for r in receipt
            if r.get("registry_number") == case["registry_number"]
            and r.get("original_name") == item.get("official_name")
            and r.get("declared_bytes") == item.get("bytes")
            and r.get("actual_bytes") == item.get("bytes")
            and r.get("sha256") == item.get("sha256")
            and r.get("status") == "OFFICIAL_BINARY_SHA_SAVED"
            and r.get("original_eis_notice_xml_sha256") == case["selected_xml_sha256"]
            and (receipt_path.parent / case["registry_number"] / str(r.get("private_filename"))).resolve() == path.resolve()
        ]
        if len(matched) != 1:
            raise ValueError("recovered legacy Word filestore receipt not matched")
        verified.append({
            "uid": uid, "file_extension": item["file_extension"],
            "actual_bytes": item["bytes"], "sha256": item["sha256"],
            "official_name": item["official_name"],
            "source_root_relative_path": item["source_root_relative_path"],
        })
    return archive, verified


def resolve_mixed_first_party_originals(
    *, source_root: Path, case: dict, pinned_case_manifest: Path,
) -> tuple[Path, list[dict]]:
    """Original mixed Oct14 first-party 11-restored + 4-old binary receipts.

    Every source binds an official selected notice XML slot/UID/name/bytes,
    its immutable first-party binary SHA, and the intact original receipt.
    """
    approved = {
        "0149200002326001555": ("epNotificationEZK2020", 1),
        "0148200000526000028": ("epNotificationEF2020", 1),
        "0349100009326000005": ("epNotificationEOK2020", 1),
    }
    identity = approved.get(case.get("registry_number"))
    if (identity is None or case.get("source_role") != "ORIGINAL_20_CORPUS"
            or (case.get("notice_type"), case.get("archived_version")) != identity
            or pinned_case_manifest.name !=
            f"APR067_R4_MIXED_FIRST_PARTY_{case['registry_number']}_2026-10-16.json"):
        raise ValueError("mixed original first-party case not approved")
    pin = json.loads(pinned_case_manifest.read_text())
    if (pin.get("registry_number") != case["registry_number"]
            or pin.get("source_role") != "ORIGINAL_20_CORPUS"
            or pin.get("selected_notice_type") != identity[0]
            or pin.get("selected_notice_version") != identity[1]
            or pin.get("selected_xml_sha256") != case["selected_xml_sha256"]
            or pin.get("archive_sha256") != case["archived_zip_sha256"]
            or not isinstance(pin.get("attachments"), list)
            or len(pin["attachments"]) != case["selected_xml_attachment_references"]):
        raise ValueError("mixed first-party source manifest mismatch")
    def checked(relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise ValueError("source path missing")
        path = source_root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(source_root) or not path.is_file():
            raise ValueError("unverified original source escapes root")
        return path
    meta_file = checked(pin["original_saved_run"] + "/metadata.json")
    if json.loads(meta_file.read_text()).get("procurement_id") != case["registry_number"]:
        raise ValueError("saved original EIS run registry mismatch")
    archive = checked(pin["archive_relative_path"])
    if sha(archive.read_bytes()) != case["archived_zip_sha256"]:
        raise ValueError("original getDocsIP archive changed")
    receipts = {}
    for name, relative_key, sha_key in (
        ("missing11", "missing11_receipt_relative_path", "missing11_receipt_sha256"),
        ("older4", "older4_receipt_relative_path", "older4_receipt_sha256"),
    ):
        rp = checked(pin[relative_key])
        if sha(rp.read_bytes()) != pin[sha_key]:
            raise ValueError("original recovered receipt SHA changed")
        receipts[name] = (rp, json.loads(rp.read_text()))
    seen = set()
    rows = []
    for slot, row in enumerate(pin["attachments"], start=1):
        uid = row.get("source_uid")
        role = row.get("source_role")
        if (not isinstance(uid, str) or not re.fullmatch(r"[0-9A-F]{32}", uid)
                or uid in seen or role not in receipts or row.get("slot") != slot):
            raise ValueError("mixed original UID/slot/source role duplicate or wrong")
        seen.add(uid)
        path = checked(row.get("source_root_relative_path"))
        if (path.suffix.lower() != row.get("file_extension")
                or path.stat().st_size != row.get("bytes")
                or sha(path.read_bytes()) != row.get("sha256")):
            raise ValueError("mixed first-party original binary SHA mismatch")
        rp, saved = receipts[role]
        if role == "missing11":
            matching = [
                x for x in saved
                if x.get("registry_number") == case["registry_number"]
                and x.get("slot_in_original_notice") == slot
                and x.get("name_in_original_notice") == row["official_name"]
                and x.get("declared_bytes") == row["bytes"]
                and x.get("actual_bytes") == row["bytes"]
                and x.get("notice_xml_sha256") == case["selected_xml_sha256"]
                and x.get("sha256") == row["sha256"]
                and x.get("state") == "VERIFIED_FIRST_PARTY_BINARY"
                and (rp.parent / case["registry_number"] / str(x.get("file"))).resolve() == path.resolve()
            ]
        else:
            matching = [
                x for x in saved
                if x.get("registry_number") == case["registry_number"]
                and x.get("display_name") == row["official_name"]
                and x.get("size") == row["bytes"]
                and x.get("source_selected_xml_sha256") == case["selected_xml_sha256"]
                and x.get("sha256") == row["sha256"]
                and (rp.parent / case["registry_number"] / str(x.get("filename"))).resolve() == path.resolve()
            ]
        if len(matching) != 1:
            raise ValueError("first-party mixed source receipt cannot be independently linked")
        rows.append({
            "uid": uid, "file_extension": row["file_extension"],
            "actual_bytes": row["bytes"], "sha256": row["sha256"],
            "official_name": row["official_name"],
            "source_root_relative_path": row["source_root_relative_path"],
        })
    return archive, rows

def prepare(
    *, stage: Path, source_root: Path, pinned_manifest: Path,
    registry_number: str = NUMBER, stage_name: str = STAGE_NAME,
    original_case_manifest: Path | None = None,
) -> dict:
    stage = stage.resolve()
    source_root = source_root.resolve()
    if stage.name != stage_name or (stage / "runs").exists():
        raise ValueError("refuse nonisolated/repeated run stage")
    if source_root.name != "ai-expert-20261012":
        raise ValueError("must use the original historical R4 development source")
    manifest = json.loads(pinned_manifest.read_text())
    record = next((r for r in manifest["cases"] if r["registry_number"] == registry_number), None)
    if record is None:
        raise ValueError("missing pinned development original source manifest")
    binaries_root = source_root / "positive-docs-recovery-20261012"
    if record["source_role"] == "ORIGINAL_20_CORPUS":
        if original_case_manifest is None:
            raise ValueError("missing original corpus first-party case manifest")
        if registry_number == "0348100024426000039":
            archived, rows = resolve_original_eok_v3(
                source_root=source_root, case=record,
                pinned_case_manifest=original_case_manifest,
            )
        elif registry_number in {
            "0127100008626000013", "0360600005326000018", "0895100000126000897",
        }:
            archived, rows = resolve_recovered_legacy_word_originals(
                source_root=source_root, case=record,
                pinned_case_manifest=original_case_manifest,
            )
        elif registry_number in {
            "0149200002326001555", "0148200000526000028", "0349100009326000005",
        }:
            archived, rows = resolve_mixed_first_party_originals(
                source_root=source_root, case=record, pinned_case_manifest=original_case_manifest,
            )
        else:
            raise ValueError("unapproved original first-party EIS case")
    elif record["source_role"] == "NEW_OFFICIAL_POSITIVE_REPLACEMENT":
        archived = source_root / "positive-eis-replacements-20261012" / registry_number / "documentation-archive.zip"
        if archived.is_symlink() or sha(archived.read_bytes()) != record["archived_zip_sha256"]:
            raise ValueError("archived EIS ZIP SHA mismatch")
        receipt_path = binaries_root / "official-21-attachments-receipt.json"
        if receipt_path.is_symlink() or sha(receipt_path.read_bytes()) != RECEIPT_PIN:
            raise ValueError("first-party R4 attachments source receipt not pinned")
        rows = [x for x in json.loads(receipt_path.read_text())["results"] if x["reg_number"] == registry_number]
    else:
        raise ValueError("source role not supported for isolated actual E2E")
    if len(rows) != record["selected_xml_attachment_references"] or not 1 <= len(rows) <= 12:
        raise ValueError("wrong original source receipt count")
    source_by_uid = {x["uid"]: x for x in rows}
    if len(source_by_uid) != len(rows):
        raise ValueError("duplicate original source uid")

    if (record.get("notice_type") not in {
        "epNotificationEF2020", "epNotificationEZK2020", "epNotificationEOK2020",
    } or not isinstance(record.get("archived_version"), int)
            or not 1 <= record["archived_version"] <= 999):
        raise ValueError("unsupported pinned historical source notice type/version")
    prefix = f"{record['notice_type']}_{registry_number}_{record['archived_version']}_"
    with zipfile.ZipFile(archived) as zip_data:
        matches = [n for n in zip_data.namelist() if n.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError("not exactly one pinned official archived notice")
        selected_raw = zip_data.read(matches[0])
        if sha(selected_raw) != record["selected_xml_sha256"]:
            raise ValueError("selected archived notice SHA mismatch")
    if b"<!DOCTYPE" in selected_raw.upper() or b"<!ENTITY" in selected_raw.upper():
        raise ValueError("unsafe XML")
    xml = ET.fromstring(selected_raw)
    from src.modules.tender_operator_agent_demo.eis_notice_parser import (
        extract_notice_attachments,
    )
    source_kinds = {
        parse_qs(urlsplit(str(item["url"])).query).get("uid", [""])[0]: item["document_kind"]
        for item in extract_notice_attachments(selected_raw.decode("utf-8"))
    }
    refs = []
    for info in xml.iter():
        if info.tag.rsplit("}", 1)[-1] != "attachmentInfo":
            continue
        row = {node.tag.rsplit("}", 1)[-1]: node.text or "" for node in info.iter()}
        url = urlsplit(row.get("url", ""))
        uid = parse_qs(url.query).get("uid", [""])[0]
        if uid not in source_by_uid or url.hostname != "zakupki.gov.ru":
            raise ValueError("official XML attachment uid/host absent")
        source = source_by_uid[uid]
        original_file = (
            source_root / source["source_root_relative_path"]
            if record["source_role"] == "ORIGINAL_20_CORPUS"
            else binaries_root / registry_number / (uid + source["file_extension"])
        )
        if (original_file.is_symlink() or not original_file.resolve().is_relative_to(source_root)
                or not original_file.is_file()
                or len(original_file.read_bytes()) != source["actual_bytes"]
                or sha(original_file.read_bytes()) != source["sha256"]
                or (record["source_role"] == "ORIGINAL_20_CORPUS"
                    and row["fileName"] != source["official_name"])
                or int(row["fileSize"]) != source["actual_bytes"]):
            raise ValueError("official binary original SHA, bytes or size conflict")
        if uid not in source_kinds or not source_kinds[uid]:
            raise ValueError("original attached document kind cannot be bound to the selected notice")
        refs.append((row["fileName"], original_file, source, source_kinds[uid]))
    if len(refs) != len(rows) or len({r[2]["uid"] for r in refs}) != len(rows):
        raise ValueError("selected archived original attachments missing")

    from src.modules.tender_operator_agent_demo import (
        procurement_intake_service as procurement,
    )
    from src.modules.tender_operator_agent_demo import upload_service as upload
    from src.modules.tender_operator_agent_demo.procurement_schemas import (
        DocsArchiveResult,
        DownloadedAttachment,
    )
    from src.modules.tender_operator_agent_demo.schemas import EisDocsArchiveRunRequest

    stage.mkdir(parents=True, exist_ok=True)
    stage.chmod(0o700)
    (stage / "runs").mkdir()
    (stage / "output").mkdir()
    os.environ["AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR"] = str(stage / "runs")
    os.environ["AI_CORP_DATABASE_URL"] = "sqlite:///" + str(stage / "offline-e2e.sqlite")

    class OfflineClient:
        def __init__(self, _settings):
            pass

        def get_docs_by_reestr_number(self, number: str, subsystem_type: str = "PRIZ"):
            if number != registry_number or subsystem_type != "PRIZ":
                raise ValueError("wrong offline historical source")
            return DocsArchiveResult(
                request_id="archived-r4-offline-readonly", status="completed",
                archive_name="documentation-archive.zip",
                archive_url="https://zakupki.gov.ru/44fz/filestore/public/1.0/download/archive",
                archive_size=archived.stat().st_size, raw_summary="OFFLINE_PRIVATE_ARCHIVE_REPLAY",
            )

    def cached_download(_client, _archive_urls, target_dir):
        dest = target_dir / "documentation-archive.zip"
        shutil.copyfile(archived, dest)
        if sha(dest.read_bytes()) != record["archived_zip_sha256"]:
            raise ValueError("source archive changed in E2E")
        return (DownloadedAttachment(
            file_name="documentation-archive.zip",
            stored_name="documentation-archive.zip",
            size_bytes=dest.stat().st_size,
            content_type="application/zip",
        ), "downloaded", [], 1)

    with (
        patch.object(procurement, "get_zakupki_soap_settings",
                     lambda: SimpleNamespace(configured=True, token_owner="offline_development")),
        patch.object(procurement, "ZakupkiSoapClient", OfflineClient),
        patch.object(procurement, "_download_archive_with_retry", cached_download),
        patch.object(procurement, "_supplement_run_with_notice_xml_attachments", lambda _run: 0),
    ):
        created = procurement.create_run_from_eis_docs_archive(
            EisDocsArchiveRunRequest(reestr_number=registry_number, analyze_after_download=False)
        )

    run_id = created.run_id
    meta = upload.load_demo_run_metadata(run_id)
    run_input = upload.get_demo_run_input_dir(run_id)
    prior_files = list(meta.get("files") or [])
    verified_binary_files = []
    for i, (official_name, original, source, official_kind) in enumerate(refs, start=1):
        relative = source["uid"] + source["file_extension"]
        target = run_input / relative
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(original, target)
        if sha(target.read_bytes()) != source["sha256"]:
            raise ValueError("original was changed during local copy")
        file_id = f"FILE-{len(prior_files) + i:02d}"
        row = upload.build_demo_file_descriptor(
            file_id=file_id, original_name=official_name, stored_name=relative,
            role_hint=procurement._role_hint_from_procurement_attachment(official_name),
            size_bytes=target.stat().st_size, content_type="application/octet-stream",
            source="eis_official_original_saved", source_type="first_party_archived_R4_verified",
            document_kind=official_kind, parent_archive="documentation-archive.zip",
        )
        meta["files"].append(row)
        verified_binary_files.append({"file_id": file_id, "stored_name": relative,
                                      "sha256": source["sha256"], "bytes": source["actual_bytes"]})
    meta["downloaded_files_count"] = len(meta["files"])
    meta["archive_extraction_complete"] = True
    meta["manual_upload_required"] = False
    upload.save_demo_run_metadata(run_id, meta)
    completeness = procurement._apply_document_set_completeness(run_id)
    meta = upload.load_demo_run_metadata(run_id)
    if meta["status"] != "ready_to_analyze":
        raise ValueError("offline official source document set incomplete: " + str(completeness))
    output = {
        "run_id": run_id,
        "registry_number": registry_number,
        "archived_eis_zip_sha256": record["archived_zip_sha256"],
        "selected_archived_notice_xml_sha256": record["selected_xml_sha256"],
        "selected_archived_version": record["archived_version"],
        "official_current_eis_version_verified": False,
        "archive_xml_originals": len(prior_files),
        "first_party_attachment_originals": verified_binary_files,
        "archive_status": meta["official_eis_procedure"]["status"],
        "doc_set_status": meta["status"],
        "all_input_sha256": [
            {"file_id": x["file_id"], "stored_name": x["stored_name"],
             "sha256": sha((run_input / x["stored_name"]).read_bytes())} for x in meta["files"]
        ],
        "blind_or_human_gold": False,
        "live_eis_calls": 0,
        "live_original_downloads": 0,
    }
    output_path = stage / "output/offline_archived_source_receipt.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    output_path.chmod(0o600)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--development-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--original-case-manifest", type=Path)
    parser.add_argument(
        "--registry", choices=(
            NUMBER, "0151600003226000011", "0152200004026000069",
            "0348100024426000021", "0348100024426000039",
            "0127100008626000013", "0360600005326000018",
            "0895100000126000897", "0149200002326001555",
            "0148200000526000028", "0349100009326000005",
        ),
        default=NUMBER,
    )
    args = parser.parse_args()
    allowed_stage = {
        NUMBER: STAGE_NAME,
        "0151600003226000011": "ta-apr067-r4-fourth-distinct-20261015",
        "0152200004026000069": "ta-apr067-r4-fifth-distinct-20261015",
        "0348100024426000021": "ta-apr067-r4-sixth-signed-zips-20261015",
        "0348100024426000039": "ta-apr067-r4-seventh-eok-revisions-20261015",
        "0127100008626000013": "ta-apr067-r4-eighth-legacy-doc-20261015",
        "0360600005326000018": "ta-apr067-r4-ninth-original-20261015",
        "0895100000126000897": "ta-apr067-r4-tenth-original-20261015",
        "0149200002326001555": "ta-apr067-r4-eleventh-quotation-20261016",
        "0148200000526000028": "ta-apr067-r4-twelfth-auction-20261016",
        "0349100009326000005": "ta-apr067-r4-thirteenth-eok-20261016",
    }[args.registry]
    if args.stage.name != allowed_stage:
        parser.error("unapproved isolated source stage")
    report = prepare(stage=args.stage, source_root=args.development_root,
                     pinned_manifest=args.manifest,
                     registry_number=args.registry, stage_name=allowed_stage,
                     original_case_manifest=args.original_case_manifest)
    print(json.dumps({
        "run_id": report["run_id"],
        "archive_xml_originals": report["archive_xml_originals"],
        "original_attachments": len(report["first_party_attachment_originals"]),
        "status": report["doc_set_status"],
        "eis_type": report["archive_status"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
