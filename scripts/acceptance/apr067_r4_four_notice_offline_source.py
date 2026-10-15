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


def prepare(*, stage: Path, source_root: Path, pinned_manifest: Path) -> dict:
    stage = stage.resolve()
    source_root = source_root.resolve()
    if stage.name != STAGE_NAME or (stage / "runs").exists():
        raise ValueError("refuse nonisolated/repeated run stage")
    if source_root.name != "ai-expert-20261012":
        raise ValueError("must use the original historical R4 development source")
    manifest = json.loads(pinned_manifest.read_text())
    record = next((r for r in manifest["cases"] if r["registry_number"] == NUMBER), None)
    if record is None or record["source_role"] != "NEW_OFFICIAL_POSITIVE_REPLACEMENT":
        raise ValueError("missing pinned development original source manifest")

    archived = source_root / "positive-eis-replacements-20261012" / NUMBER / "documentation-archive.zip"
    if archived.is_symlink() or sha(archived.read_bytes()) != record["archived_zip_sha256"]:
        raise ValueError("archived EIS ZIP SHA mismatch")
    binaries_root = source_root / "positive-docs-recovery-20261012"
    receipt_path = binaries_root / "official-21-attachments-receipt.json"
    if receipt_path.is_symlink() or sha(receipt_path.read_bytes()) != RECEIPT_PIN:
        raise ValueError("first-party R4 attachments source receipt not pinned")
    rows = [x for x in json.loads(receipt_path.read_text())["results"] if x["reg_number"] == NUMBER]
    if len(rows) != record["selected_xml_attachment_references"] or len(rows) != 5:
        raise ValueError("incorrect five original source receipts")
    source_by_uid = {x["uid"]: x for x in rows}
    if len(source_by_uid) != 5:
        raise ValueError("duplicate original source uid")

    with zipfile.ZipFile(archived) as zip_data:
        matches = [n for n in zip_data.namelist()
                   if n.startswith(f"epNotificationEF2020_{NUMBER}_4_")]
        if len(matches) != 1:
            raise ValueError("not exactly one v4 official archived notice")
        selected_raw = zip_data.read(matches[0])
        if sha(selected_raw) != record["selected_xml_sha256"]:
            raise ValueError("selected archived v4 notice SHA mismatch")
    if b"<!DOCTYPE" in selected_raw.upper() or b"<!ENTITY" in selected_raw.upper():
        raise ValueError("unsafe XML")
    xml = ET.fromstring(selected_raw)
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
        original_file = binaries_root / NUMBER / (uid + source["file_extension"])
        if (original_file.is_symlink() or not original_file.is_file()
                or len(original_file.read_bytes()) != source["actual_bytes"]
                or sha(original_file.read_bytes()) != source["sha256"]
                or int(row["fileSize"]) != source["actual_bytes"]):
            raise ValueError("official binary original SHA, bytes or size conflict")
        refs.append((row["fileName"], original_file, source))
    if len(refs) != 5 or len({r[2]["uid"] for r in refs}) != 5:
        raise ValueError("selected v4 original attachments missing")

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
            if number != NUMBER or subsystem_type != "PRIZ":
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
            EisDocsArchiveRunRequest(reestr_number=NUMBER, analyze_after_download=False)
        )

    run_id = created.run_id
    meta = upload.load_demo_run_metadata(run_id)
    run_input = upload.get_demo_run_input_dir(run_id)
    prior_files = list(meta.get("files") or [])
    verified_binary_files = []
    for i, (official_name, original, source) in enumerate(refs, start=1):
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
            parent_archive="documentation-archive.zip",
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
        "registry_number": NUMBER,
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
    args = parser.parse_args()
    report = prepare(stage=args.stage, source_root=args.development_root,
                     pinned_manifest=args.manifest)
    print(json.dumps({
        "run_id": report["run_id"],
        "archive_xml_originals": report["archive_xml_originals"],
        "original_attachments": len(report["first_party_attachment_originals"]),
        "status": report["doc_set_status"],
        "eis_type": report["archive_status"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
