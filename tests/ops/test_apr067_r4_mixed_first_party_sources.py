"""Original split-receipt EIS sources reject altered bytes, IDs and editions."""
import hashlib
import json

import pytest

from scripts.acceptance.apr067_r4_four_notice_offline_source import (
    resolve_mixed_first_party_originals,
)

CASES = [
    ("0149200002326001555", "epNotificationEZK2020"),
    ("0148200000526000028", "epNotificationEF2020"),
    ("0349100009326000005", "epNotificationEOK2020"),
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fixture(tmp_path, reg, kind):
    root = tmp_path / "originals"
    base = root / "tender_operator_demo/run"
    (base / "input").mkdir(parents=True)
    archive = base / "input/documentation-archive.zip"
    archive.write_bytes(b"saved getdocs original")
    (base / "metadata.json").write_text(json.dumps({"procurement_id": reg}))
    receipts = {}
    rows = []
    for slot, role in [(1, "missing11"), (2, "older4")]:
        parent = root / ("competitive-missing-11-originals-20261014" if slot == 1 else "competitive-older-missing-4-originals-20261014")
        parent.mkdir()
        name = f"original {slot}.docx"
        f = parent / reg / f"attachment-{slot}.docx"
        f.parent.mkdir()
        f.write_bytes(f"original-{slot}".encode())
        rows.append({"source_uid": f"{slot:032X}", "slot": slot, "source_role": role, "official_name": name,
                         "bytes": f.stat().st_size, "sha256": digest(f), "file_extension": ".docx",
                         "source_root_relative_path": str(f.relative_to(root))})
        if slot == 1:
            receipts["missing11"] = (parent / "private-source-receipt.json", [
                {"registry_number": reg, "slot_in_original_notice": slot, "name_in_original_notice": name,
                     "declared_bytes": f.stat().st_size, "actual_bytes": f.stat().st_size, "notice_xml_sha256": "a"*64,
                     "sha256": digest(f), "state": "VERIFIED_FIRST_PARTY_BINARY", "file": f.name}])
        else:
            receipts["older4"] = (parent / "four-older-contract-originals-private.json", [
                {"registry_number": reg, "display_name": name, "size": f.stat().st_size,
                     "source_selected_xml_sha256": "a"*64, "sha256": digest(f), "filename": f.name}])
    for p, obj in receipts.values():
        p.write_text(json.dumps(obj))
    meta={"registry_number": reg, "source_role": "ORIGINAL_20_CORPUS", "archived_version": 1,
              "notice_type": kind, "archived_zip_sha256": digest(archive), "selected_xml_sha256": "a"*64,
              "selected_xml_attachment_references": 2}
    pin={"registry_number": reg,"source_role": "ORIGINAL_20_CORPUS",
             "selected_notice_type": kind,"selected_notice_version": 1,
             "selected_xml_sha256": "a"*64,"archive_sha256": digest(archive),
             "original_saved_run": str(base.relative_to(root)),
             "archive_relative_path": str(archive.relative_to(root)),"attachments": rows}
    for key,(p,_) in receipts.items():
        pin[key+"_receipt_relative_path"]=str(p.relative_to(root))
        pin[key+"_receipt_sha256"]=digest(p)
    manifest = tmp_path / f"APR067_R4_MIXED_FIRST_PARTY_{reg}_2026-10-16.json"
    manifest.write_text(json.dumps(pin))
    return root, meta, manifest


@pytest.mark.parametrize("reg,kind",CASES)
def test_both_independent_original_receipts_pass(tmp_path,reg,kind):
    root,meta,path=fixture(tmp_path,reg,kind)
    archive,files=resolve_mixed_first_party_originals(source_root=root,case=meta,pinned_case_manifest=path)
    assert archive.name=="documentation-archive.zip" and len(files)==2


@pytest.mark.parametrize("reg,kind",CASES)
@pytest.mark.parametrize("tamper",["sha","uid","slot","version","path","receipt11","receipt4","role"])
def test_modified_originals_block_model(tmp_path,reg,kind,tamper):
    root,meta,path=fixture(tmp_path,reg,kind)
    data=json.loads(path.read_text())
    if tamper=="sha":data["attachments"][0]["sha256"]="0"*64
    if tamper=="uid":data["attachments"][1]["source_uid"]=data["attachments"][0]["source_uid"]
    if tamper=="slot":data["attachments"][1]["slot"]=1
    if tamper=="version":data["selected_notice_version"]=2
    if tamper=="path":data["attachments"][0]["source_root_relative_path"]="../outside"
    if tamper=="receipt11":data["missing11_receipt_sha256"]="0"*64
    if tamper=="receipt4":data["older4_receipt_sha256"]="0"*64
    if tamper=="role":data["attachments"][0]["source_role"]="unknown"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        resolve_mixed_first_party_originals(source_root=root,case=meta,pinned_case_manifest=path)
