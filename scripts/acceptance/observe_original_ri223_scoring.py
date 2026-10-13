"""Read-only, pinned original RI223 evaluation observation; never a GO/NO_GO.

Requires local original getDocsIP ZIP and its attached RAR. No network calls.
With intentionally different scoring formula/lot evidence, abstains.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from src.modules.company_profile_store.qualification_223_observer import (
    observe_ri223_scoring_text,
    verify_ri223_originals,
)


def _extract_original_pdf(rar_path: Path, member_name: str) -> bytes:
    if rar_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Original RAR exceeds byte limit")
    result = subprocess.run(
        ["bsdtar", "-xOf", str(rar_path), member_name],
        capture_output=True,
        timeout=20,
        check=True,
    )
    if not result.stdout.startswith(b"%PDF-") or len(result.stdout) > 8 * 1024 * 1024:
        raise ValueError("Original RAR member is not a bounded PDF")
    return result.stdout


def _pdf_text(original_pdf_bytes: bytes) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=original_pdf_bytes,
        capture_output=True,
        timeout=20,
        check=True,
    )
    if len(result.stdout) > 1_000_000:
        raise ValueError("Original PDF text too long for narrow scoring observer")
    return result.stdout.decode("utf-8", errors="strict")


def replay(*, soap_archive: Path, rar_archive: Path, receipt_file: Path) -> dict:
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    soap_bytes = soap_archive.read_bytes()
    rar_bytes = rar_archive.read_bytes()
    original_pdf = _extract_original_pdf(
        rar_archive, str(receipt["evaluation_pdf_member"])
    )
    trusted = verify_ri223_originals(
        soap_bytes, rar_bytes, original_pdf, receipt
    )
    scoring = observe_ri223_scoring_text(_pdf_text(original_pdf))
    return {
        **trusted,
        **scoring,
        "digital_signature_verified": False,
        "source_document_format": "PDF_INSIDE_RAR_ATTACHMENT",
        "source_inner_pdf_member": receipt["evaluation_pdf_member"],
        "original_eis_readonly": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soap-archive", required=True, type=Path)
    parser.add_argument("--rar-archive", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        replay(
            soap_archive=args.soap_archive,
            rar_archive=args.rar_archive,
            receipt_file=args.receipt,
        ),
        ensure_ascii=False,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
