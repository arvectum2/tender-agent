"""Read-only source-pinned alternate EOK2020 scoring PDF observation.

No ETP, no tenant-profile inference, no legal or competitive GO/NO_GO.
Requires private original getDocsIP ZIP and originally downloaded evaluation PDF.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from src.modules.company_profile_store.qualification_44_alternate_observer import (
    observe_44_alternate_pdf_text,
    verify_44_alternate_originals,
)


def replay(*, original_soap_zip: Path, original_pdf: Path, receipt_file: Path) -> dict:
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    original_pdf_bytes = original_pdf.read_bytes()
    proven = verify_44_alternate_originals(
        soap_archive_bytes=original_soap_zip.read_bytes(),
        scoring_pdf_bytes=original_pdf_bytes,
        receipt=receipt,
    )
    result = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=original_pdf_bytes,
        capture_output=True,
        timeout=20,
        check=True,
    )
    if len(result.stdout) > 1_000_000:
        raise ValueError("Unbounded original evaluation PDF text")
    weights = observe_44_alternate_pdf_text(result.stdout.decode("utf-8"))
    return {**proven, **weights, "original_eis_readonly": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soap-archive", type=Path, required=True)
    parser.add_argument("--scoring-pdf", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(
        original_soap_zip=args.soap_archive,
        original_pdf=args.scoring_pdf,
        receipt_file=args.receipt,
    ), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
