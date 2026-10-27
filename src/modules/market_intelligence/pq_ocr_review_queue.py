"""Create a provisional ChatGPT review packet from OCR of a SHA-verified scan.

OCR quotations are derived/unverified, NOT exact original-document text.
Never overwrite the earlier pending native-text packet.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from .pq_review_queue import _atomic


def enqueue_ocr(*, original_pdf: Path, ocr_json: Path, queue_dir: Path,
                registry_number: str) -> dict:
    if original_pdf.is_symlink() or not original_pdf.is_file() or original_pdf.suffix.lower() != ".pdf":
        raise ValueError("Invalid original PDF")
    import re
    if not re.fullmatch(r"[0-9]{11}|[0-9]{19,20}", registry_number):
        raise ValueError("Invalid registry")
    result = json.loads(ocr_json.read_text(encoding="utf-8"))
    sha = hashlib.sha256(original_pdf.read_bytes()).hexdigest()
    if result.get("source_sha256") != sha or result.get("status") != "ocr_unverified":
        raise ValueError("Missing verified original SHA/derived OCR")
    text = result.get("text", "")[:30000]
    if len(" ".join(text.split())) < 50:
        raise ValueError("No reviewable OCR text")
    derived_sha = hashlib.sha256(text.encode()).hexdigest()
    identity = registry_number + "-" + hashlib.sha256(
        (sha + derived_sha).encode()).hexdigest()[:24]
    packet = {"schema_version": "pq-chatgpt-review-packet/1",
              "registry_number": registry_number,
              "documents": [{"filename": original_pdf.name,
                             "sha256": sha, "text": text, "method": "ocr_unverified",
                             "derived_ocr_sha256": derived_sha,
                             "visual_verification_required": True,
                             "lexical_hints_only": []}],
              "review_instructions": "OCR transcription is uncertain. Classify scope provisionally; never verify a signed contract, supplier identity or award without checking the original scan.",
              "llm_executed": False, "market_total_rub": None}
    item = {"schema_version": "pq-review-queue/1", "id": identity,
            "state": "pending_review", "packet": packet, "review": None}
    target = queue_dir / (identity + ".json")
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        if previous["packet"] != packet:
            raise ValueError("OCR identity conflict")
        return previous
    _atomic(target, item)
    return item


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--ocr", type=Path, required=True)
    p.add_argument("--queue-dir", type=Path, required=True)
    p.add_argument("--registry", required=True)
    a = p.parse_args()
    result = enqueue_ocr(original_pdf=a.pdf, ocr_json=a.ocr,
                         queue_dir=a.queue_dir, registry_number=a.registry)
    print(json.dumps({"id": result["id"], "state": result["state"]}))


if __name__ == "__main__": main()
