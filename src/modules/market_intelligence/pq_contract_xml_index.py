"""Conservative exact-number procurement-to-contract evidence from local 223-FZ XML ZIP.

Archive presence proves neither contract signing nor supplier identity.
Report contract register fields with source SHA, leaving signatory and signed
sum unverified until independently corroborated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_ZIP_BYTES = 200_000_000
MAX_XML_BYTES = 10_000_000


def _child(node: ET.Element | None, key: str) -> ET.Element | None:
    if node is None:
        return None
    return next((x for x in node if x.tag.rsplit("}", 1)[-1] == key), None)


def _value(node: ET.Element | None, *path: str) -> str | None:
    for key in path:
        node = _child(node, key)
    text = (node.text or "").strip() if node is not None else ""
    return text or None


def scan(root: Path, leads: Path, max_archives: int = 100) -> dict:
    if root.is_symlink() or not root.is_dir() or not 1 <= max_archives <= 500:
        raise ValueError("Invalid contract source scope")
    lead_rows = json.loads(leads.read_text(encoding="utf-8"))["records"]
    numbers = {str(row.get("procedure_id")) for row in lead_rows}
    archives = sorted(root.glob("*/archive-*/documentation-archive.zip"))
    found = []
    problems = []
    inspected = 0
    for archive in archives[:max_archives]:
        if archive.is_symlink() or archive.stat().st_size > MAX_ZIP_BYTES:
            problems.append({"archive": str(archive), "reason": "unsafe_archive"})
            continue
        inspected += 1
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        try:
            with zipfile.ZipFile(archive) as zip_file:
                members = zip_file.infolist()
                if len(members) > 1000:
                    raise ValueError("xml_member_budget")
                for member in members:
                    if not member.filename.endswith(".xml") or member.file_size > MAX_XML_BYTES:
                        continue
                    content = zip_file.read(member)
                    element = ET.fromstring(content)
                    if element.tag.rsplit("}", 1)[-1] != "contractCutted":
                        continue
                    contract = _child(_child(_child(element, "body"), "item"), "contractData")
                    notice = _value(contract, "purchaseNoticeInfo", "purchaseNoticeNumber")
                    if notice not in numbers or not re.fullmatch(r"[0-9]{11}", notice):
                        continue
                    found.append({
                        "procedure_id": notice,
                        "contract_register_number": _value(contract, "contractRegNumber"),
                        "contract_record_registration_number": _value(contract, "registrationNumber"),
                        "contract_document_date": _value(contract, "contractDate"),
                        "lot_number": _value(contract, "lotNum"),
                        "subject": _value(contract, "subjectContract"),
                        "price_text": _value(contract, "price"),
                        "ruble_price_text": _value(contract, "rubPrice"),
                        "record_status_code": _value(contract, "status"),
                        "customer_name": _value(contract, "customer", "mainInfo", "fullName"),
                        "customer_inn": _value(contract, "customer", "mainInfo", "inn"),
                        "supplier_verified": False,
                        "signed_contract_verified": False,
                        "price_verification": "official_contract_registry_xml_field_not_signed_sum",
                        "source_archive": str(archive),
                        "source_archive_sha256": archive_sha,
                        "source_xml_member": member.filename,
                        "source_xml_sha256": hashlib.sha256(content).hexdigest(),
                    })
        except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
            problems.append({"archive": str(archive), "reason": type(exc).__name__})
    return {"schema_version": "pq-contract-register-xml-evidence/1",
            "lead_count": len(lead_rows), "archives_inspected": inspected,
            "records": found, "errors": problems,
            "scope": "local_registry_xml_only_not_all_awards"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--leads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = scan(args.root, args.leads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({"archives_inspected": output["archives_inspected"],
                      "records_matched": len(output["records"]),
                      "errors": len(output["errors"])}))


if __name__ == "__main__":
    main()
