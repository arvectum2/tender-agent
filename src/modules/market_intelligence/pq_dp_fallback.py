"""Recover readable PDF text when Data Platform extraction returns empty.

Preserves Data Platform provenance and records the fallback extractor explicitly.
Never treats an empty PDF as a verified absence of evidence.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def pdf_text_fallback(path: Path, *, max_chars: int = 100000) -> dict:
    if path.suffix.lower() != ".pdf" or path.is_symlink() or not path.is_file():
        raise ValueError("Only local regular PDF files supported")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("PDF exceeds safety budget")
    proc = subprocess.run(["/opt/homebrew/bin/pdftotext", "-layout",
                           str(path), "-"], capture_output=True,
                          timeout=30, check=False)
    text = proc.stdout.decode("utf-8", errors="replace")[:max_chars] if proc.returncode == 0 else ""
    return {"method": "pdftotext_native_fallback",
            "status": "extracted" if text.strip() else "unresolved_needs_ocr",
            "characters": len(text), "text": text}
