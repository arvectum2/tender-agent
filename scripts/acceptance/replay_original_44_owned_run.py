"""Replay one source-attested 44-FZ original ZIP/PDF through the report service.

Read-only with respect to the original ZIP and PDF and all persisted tenant data.
The replay constructs TEMPORARY metadata from pinned receipt values; it is NOT
proof of a production SaaS tenant import or verified EIS digital signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.modules.company_profile_store import qualification_run_service as service


def _original_digest(path: Path, expected: str, *, max_bytes: int) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_bytes:
        raise ValueError("Missing, symlinked or oversized original source file")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Pinned original EIS source checksum mismatch")


def replay_original_owned_run(
    *, soap_archive: Path, evaluation_pdf: Path,
    receipt_path: Path, as_of: date,
) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema_version") != "eis-original-composite-scoring-receipt-v1"
        or receipt.get("procurement_law") != "44fz"
        or not str(receipt.get("procurement_number", "")).isdigit()
        or len(str(receipt["procurement_number"])) != 19
    ):
        raise ValueError("Unsupported original 44-FZ scoring receipt")
    _original_digest(
        soap_archive, receipt["original_soap_archive_sha256"],
        max_bytes=16 * 1024 * 1024,
    )
    _original_digest(
        evaluation_pdf, receipt["scoring_document_sha256"],
        max_bytes=8 * 1024 * 1024,
    )
    if evaluation_pdf.stat().st_size != receipt["scoring_document_size_bytes"]:
        raise ValueError("Original EIS PDF size differs from receipt")
    uid = receipt["scoring_document_uid"]
    if not isinstance(uid, str) or len(uid) != 32:
        raise ValueError("Unexpected EIS source UID")

    with tempfile.TemporaryDirectory(prefix="ta-eis-source-report-replay-") as temp:
        folder = Path(temp)
        shutil.copyfile(soap_archive, folder / "original-eis.zip")
        shutil.copyfile(evaluation_pdf, folder / "original-evaluation.pdf")
        metadata = {
            "procurement_source": "zakupki_gov_ru_getdocs_ip",
            "reestr_number": receipt["procurement_number"],
            "archive_downloaded": True,
            "getdocs_status": "completed",
            "subsystem_type": "PRIZ",
            "token_owner": "individual",
            "archive_source_host": "int.zakupki.gov.ru",
            "archive_stored_name": "original-eis.zip",
            "original_getdocs_archive_sha256": receipt["original_soap_archive_sha256"],
            "files": [{
                "source_type": "notice_xml_attachments",
                "original_name": receipt["scoring_document_name"],
                "stored_name": "original-evaluation.pdf",
                "source_download_sha256": receipt["scoring_document_sha256"],
                "source_url": (
                    "https://zakupki.gov.ru/44fz/filestore/public/1.0/"
                    "download/priz/file.html?uid=" + uid
                ),
            }],
        }

        def run_once() -> dict:
            with (
                patch.object(service, "load_demo_run_metadata", return_value=metadata),
                patch.object(service, "get_demo_run_input_dir", return_value=folder),
            ):
                return service.assess_owned_run_qualification(
                    None,
                    run_id="toa-run-20261013000000-a1b2c3",
                    customer_id="offline-replay-not-a-live-tenant",
                    as_of=as_of,
                )

        first = run_once()
        criteria = first.get("criterion_source") or {}
        if not (
            first.get("competitive_recommendation") == "NOT_ASSESSED"
            and first.get("source_status")
            == "ORIGINAL_EIS_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED"
            and criteria.get("price_weight_percent") == 60
            and criteria.get("qualification_weight_percent") == 40
            and criteria.get("qualification_subweights_percent")
            == {"completed_contract_count": 5, "specialists": 95}
            and first.get("qualifying_contracts") is None
            and first.get("external_action_allowed") is False
            and first.get("human_gold") is False
        ):
            raise ValueError("Actual-source report disagrees with pinned supported rubric")
        original_copy = folder / "original-evaluation.pdf"
        pdf_bytes = original_copy.read_bytes()
        original_copy.write_bytes(pdf_bytes[:-1] + bytes([pdf_bytes[-1] ^ 1]))
        tampered = run_once()
        if not (
            tampered.get("competitive_recommendation") == "NOT_ASSESSED"
            and tampered.get("source_status")
            == "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
            and "criterion_source" not in tampered
        ):
            raise ValueError("Tampered original PDF was not rejected by run service")
    return {
        "procurement_number": receipt["procurement_number"],
        "observation_as_of": as_of.isoformat(),
        "original_eis_source_sha256": receipt["original_soap_archive_sha256"],
        "original_evaluation_pdf_sha256": receipt["scoring_document_sha256"],
        "source_status": first["source_status"],
        "price_weight_percent": criteria["price_weight_percent"],
        "qualification_weight_percent": criteria["qualification_weight_percent"],
        "qualification_subweights_percent": criteria["qualification_subweights_percent"],
        "competitive_recommendation": first["competitive_recommendation"],
        "human_gold": False,
        "digital_signature_verified": False,
        "external_action_allowed": False,
        "tampered_copy_source_status": tampered["source_status"],
        "tenant_database_accessed": False,
        "production_saas_login_tested": False,
        "original_documents_modified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soap-archive", type=Path, required=True)
    parser.add_argument("--scoring-pdf", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    result = replay_original_owned_run(
        soap_archive=args.soap_archive,
        evaluation_pdf=args.scoring_pdf,
        receipt_path=args.receipt,
        as_of=args.as_of,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
