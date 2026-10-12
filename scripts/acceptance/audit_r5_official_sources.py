"""Reproducible read-only source/receipt alignment for archived EIS R5 cases.

NOT: independent human approval, commercial fitness or live EIS procedure status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

REG_NUMBER = re.compile(r"\d{19}\Z")
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 200
MAX_XML_BYTES = 8 * 1024 * 1024


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_notice(xml: bytes, registry_number: str) -> list[dict]:
    """Only the notice's direct versionNumber is authoritative.

    Descendant nested versionNumber may belong to an unrelated payload.
    """
    if len(xml) > MAX_XML_BYTES or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("unsafe_or_oversized_xml")
    root = ET.fromstring(xml)
    matches = []
    for notice in root.iter():
        if not local_name(notice.tag).startswith("epNotification"):
            continue
        numbers = [(x.text or "").strip() for x in notice.iter()
                   if local_name(x.tag) == "purchaseNumber"]
        if registry_number not in numbers:
            continue
        direct = [(x.text or "").strip() for x in notice
                  if local_name(x.tag) == "versionNumber"]
        if len(direct) != 1 or not direct[0].isdecimal():
            raise ValueError("ambiguous_notice_version")
        version = int(direct[0])
        if version > 999:
            raise ValueError("unsafe_notice_version")
        def raw_values(key: str, *, node: ET.Element = notice) -> list[str]:
            return list(dict.fromkeys((x.text or "").strip() for x in node.iter()
                if local_name(x.tag) == key and (x.text or "").strip()))
        amounts = raw_values("maxPrice")
        try:
            canonical_prices = list(dict.fromkeys(Decimal(v) for v in amounts))
        except InvalidOperation:
            canonical_prices = []
        deadlines = raw_values("endDT")
        publications = raw_values("publishDTInEIS")
        matches.append({
            "version": version,
            "notice_type": local_name(notice.tag),
            "endDT": deadlines[0] if len(deadlines) == 1 else None,
            "endDT_ambiguity": len(deadlines) > 1,
            "maxPrice": str(canonical_prices[0]) if len(canonical_prices) == 1 else None,
            "maxPrice_ambiguity": len(canonical_prices) > 1,
            "publishDTInEIS": publications[0] if len(publications) == 1 else None,
            "publishedContentId_count": len(raw_values("publishedContentId")),
        })
    return matches


def audit_archive(archive_path: Path, reg_number: str) -> dict:
    if not REG_NUMBER.fullmatch(reg_number):
        raise ValueError("unsafe_registry_number")
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("archive_too_large")
    archive_bytes = archive_path.read_bytes()
    documents: list[dict] = []
    sha_map: dict[str, dict] = {}
    with zipfile.ZipFile(archive_path) as zipped:
        members = [item for item in zipped.infolist() if not item.is_dir()]
        if len(members) > MAX_MEMBERS or sum(x.file_size for x in members) > MAX_ARCHIVE_BYTES:
            raise ValueError("zip_bomb_or_too_many_members")
        if len({x.filename for x in members}) != len(members):
            raise ValueError("duplicate_archive_member")
        for member in members:
            if ".." in Path(member.filename).parts or member.filename.startswith("/"):
                raise ValueError("unsafe_archive_member_name")
            if not member.filename.lower().endswith(".xml"):
                continue
            raw = zipped.read(member)
            signature = hashlib.sha256(raw).hexdigest()
            entries = parse_notice(raw, reg_number)
            entry = {"sha256": signature, "bytes": len(raw), "notices": entries}
            documents.append(entry)
            sha_map[signature] = entry
    notice_files = [entry for entry in documents if entry["notices"]]
    candidates = [dict(n, xml_sha256=f["sha256"]) for f in notice_files
                  for n in f["notices"]]
    candidates.sort(key=lambda d: (d["version"], d["xml_sha256"]))
    if not candidates:
        raise ValueError("no_number_matched_notice_xml")
    max_version = candidates[-1]["version"]
    highest = [x for x in candidates if x["version"] == max_version]
    if len({(x["endDT"], x["maxPrice"], x["notice_type"]) for x in highest}) > 1:
        raise ValueError("conflicting_highest_notice_facts")
    latest = highest[-1]
    return {
        "zip_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "xml_file_count": len(documents),
        "notice_record_count": len(candidates),
        "archived_versions": sorted({x["version"] for x in candidates}),
        "highest": latest,
        "sha_map": sha_map,
    }


def reconcile(receipts: list[dict], transport: dict, archive_dir: Path,
              persisted: dict) -> list[dict]:
    fetched = {x["reg_number"]: x for x in transport["cases"]}
    stored = {x["reg_number"]: x for x in persisted["cases"]}
    rows = []
    for case in receipts:
        reg = case["reg_number"]
        fetch = fetched[reg]
        saved = stored[reg]
        out = {
            "reg_number": reg,
            "transport": fetch["transport"],
            "official_archive_sha256": fetch.get("fresh_official_zip_sha256"),
            "fresh_archive_same_as_prior": fetch.get("zip_same_as_prior"),
            "historic_receipt_files": len(case["document_files"]),
            "historic_stored_file_sha_matched": saved["raw_file_matched"],
            "historic_stored_file_sha_mismatched": len(saved["raw_file_mismatches"]),
            "historic_stored_report_present": saved["stored_report"],
            "historic_stored_recommendation": saved["stored_recommendation"],
            "notice_receipt_sha256": case.get("notice_sha256"),
            "notice_receipt_in_official_xml": False,
            "old_notice_archived_version": None,
            "last_archived_version": None,
            "archived_versions": [],
            "latest_notice_xml_sha256": None,
            "latest_endDT": None,
            "latest_maxPrice": None,
            "latest_notice_type": None,
            "source_receipt_files_present_in_fresh_xml_zip": 0,
            "selected_notice_stale_vs_archive": None,
            "technical_disposition": "NO_OFFICIAL_ARCHIVE",
            "human_signoff": False,
        }
        if fetch["transport"] == "completed":
            archive = audit_archive(archive_dir / reg / "documentation-archive.zip", reg)
            if archive["zip_sha256"] != out["official_archive_sha256"]:
                raise ValueError("official_archive_hash_mismatch")
            out.update({
                "last_archived_version": archive["highest"]["version"],
                "archived_versions": archive["archived_versions"],
                "latest_notice_xml_sha256": archive["highest"]["xml_sha256"],
                "latest_endDT": archive["highest"]["endDT"],
                "latest_maxPrice": archive["highest"]["maxPrice"],
                "latest_notice_type": archive["highest"]["notice_type"],
            })
            matches = archive["sha_map"]
            out["source_receipt_files_present_in_fresh_xml_zip"] = sum(
                f["sha256"] in matches for f in case["document_files"])
            receipt_sha = case.get("notice_sha256")
            if receipt_sha in matches:
                out["notice_receipt_in_official_xml"] = True
                versions = [i["version"] for i in matches[receipt_sha]["notices"]]
                if len(versions) == 1:
                    out["old_notice_archived_version"] = versions[0]
                    out["selected_notice_stale_vs_archive"] = (
                        versions[0] < archive["highest"]["version"]
                    )
            if not out["notice_receipt_in_official_xml"]:
                out["technical_disposition"] = "RECEIPT_NOTICE_NOT_IN_OFFICIAL_ZIP"
            elif out["selected_notice_stale_vs_archive"]:
                out["technical_disposition"] = "HISTORICAL_RECEIPT_OLDER_THAN_ARCHIVE"
            else:
                out["technical_disposition"] = "RECEIPT_NOTICE_PRESENT_IN_OFFICIAL_ARCHIVE"
        rows.append(out)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts",type=Path,required=True)
    parser.add_argument("--transport",type=Path,required=True)
    parser.add_argument("--archive-dir",type=Path,required=True)
    parser.add_argument("--stored",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    receipt=json.loads(args.receipts.read_text())["cases"]
    assert len(receipt)==20 and len({x["reg_number"] for x in receipt})==20
    rows=reconcile(receipt,json.loads(args.transport.read_text()),
                   args.archive_dir,json.loads(args.stored.read_text()))
    total_docs=sum(x["historic_receipt_files"] for x in rows)
    summary={
        "scope":"INDEPENDENT_SOURCE_BYTES_READONLY_CHECK_NOT_HUMAN_SIGNOFF",
        "cases":len(rows),"fresh_official_zip_count":sum(x["transport"]=="completed" for x in rows),
        "no_data":sum(x["transport"]=="no_data" for x in rows),
        "stored_file_SHA_count":sum(x["historic_stored_file_sha_matched"] for x in rows),
        "stored_file_receipts":total_docs,
        "receipt_file_SHA_matches_official_XML":sum(x["source_receipt_files_present_in_fresh_xml_zip"] for x in rows),
        "notice_source_SHA_matches_official_zip":sum(x["notice_receipt_in_official_xml"] for x in rows),
        "notice_revision_stale_count":sum(x["selected_notice_stale_vs_archive"] is True for x in rows),
        "historic_reports":sum(x["historic_stored_report_present"] for x in rows),
        "human_signed":0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"summary":summary,"cases":rows},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False))
    for r in rows:
        print("SOURCE_CASE",r["reg_number"],"versions",r["archived_versions"],
              "receipt_v",r["old_notice_archived_version"],"status",r["technical_disposition"],
              "XML",r["source_receipt_files_present_in_fresh_xml_zip"],
              "of",r["historic_receipt_files"])
if __name__=="__main__":
    main()
