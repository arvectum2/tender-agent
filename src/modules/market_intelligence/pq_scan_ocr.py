"""Explicit bounded OCR fallback for scanned official-source PDF evidence.

OCR is a derived, error-prone reading aid, not independent signed-contract
evidence. Caller must retain the immutable original PDF and its SHA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PDFINFO = "/opt/homebrew/bin/pdfinfo"
PDFTOPPM = "/opt/homebrew/bin/pdftoppm"
TESSERACT = "/opt/homebrew/bin/tesseract"


def ocr_pdf(path: Path, *, max_pages: int = 5, max_bytes: int = 20_000_000) -> dict:
    if path.suffix.lower() != ".pdf" or not path.is_file() or path.is_symlink():
        raise ValueError("Expected local non-symlink PDF")
    if not 1 <= max_pages <= 10 or path.stat().st_size > max_bytes:
        raise ValueError("PDF/OCR budget exceeded")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    info = subprocess.run([PDFINFO, str(path)], capture_output=True, timeout=15, check=False)
    match = re.search(rb"(?m)^Pages:\s*([0-9]+)", info.stdout)
    if info.returncode != 0 or not match:
        return {"status": "pdf_page_count_unavailable", "source_sha256": sha, "text": ""}
    total = int(match.group(1))
    pages = []
    for page in range(1, min(total, max_pages) + 1):
        picture = subprocess.run(
            [PDFTOPPM, "-f", str(page), "-l", str(page), "-scale-to",
             "1400", "-png", "-singlefile", str(path)],
            capture_output=True, timeout=30, check=False)
        if picture.returncode != 0 or not picture.stdout.startswith(b"\x89PNG"):
            pages.append({"page": page, "status": "render_failed", "text": ""})
            continue
        result = subprocess.run(
            [TESSERACT, "stdin", "stdout", "-l", "rus+eng"],
            input=picture.stdout, capture_output=True, timeout=35, check=False)
        text = result.stdout.decode("utf-8", errors="replace")[:20000] if result.returncode == 0 else ""
        pages.append({"page": page, "status": "ocr_unverified" if text.strip() else "empty",
                      "text": text})
    text = "\n\n".join(p["text"] for p in pages)
    return {"status": "ocr_unverified" if text.strip() else "unresolved",
            "source_sha256": sha, "pages_total": total,
            "pages_processed": len(pages), "pages": pages,
            "text": text, "method": "tesseract_rus_eng_1400px"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-pages", type=int, default=5)
    a = p.parse_args()
    result = ocr_pdf(a.pdf, max_pages=a.max_pages)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({"status": result["status"], "pages": result.get("pages_processed", 0),
                      "characters": len(result["text"]), "source_sha256": result["source_sha256"]}))


if __name__ == "__main__": main()
