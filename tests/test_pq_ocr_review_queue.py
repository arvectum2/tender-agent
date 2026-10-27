import hashlib
import json

import pytest

from src.modules.market_intelligence.pq_arc_chat import next_packet
from src.modules.market_intelligence.pq_ocr_review_queue import enqueue_ocr
from src.modules.market_intelligence.pq_review_queue import accept


def test_ocr_queue_source_SHA_and_visual_review(tmp_path):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF example scanned")
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    derived = tmp_path / "ocr.json"
    derived.write_text(json.dumps({
        "status": "ocr_unverified", "source_sha256": sha,
        "text": "The original scan mentions 6 kV dynamic reactive compensation"}))
    queue = tmp_path / "queue"
    first = enqueue_ocr(original_pdf=original, ocr_json=derived, queue_dir=queue,
                        registry_number="32616280467")
    again = enqueue_ocr(original_pdf=original, ocr_json=derived, queue_dir=queue,
                        registry_number="32616280467")
    assert first["id"] == again["id"]
    next_item = next_packet(queue_dir=queue)
    assert next_item["id"] == first["id"]
    result = accept(queue_dir=queue, identity=first["id"], review={
        "registry_number": "32616280467", "classification": "uncertain",
        "evidence": [{"sha256": sha, "quote": "dynamic reactive compensation"}],
        "reasoning": "OCR must be visually verified"})
    assert result["review"]["ocr_requires_visual_verification"] is True
    assert result["review"]["signed_contract_verified"] is False


def test_ocr_queue_rejects_wrong_source(tmp_path):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF different")
    derived = tmp_path / "ocr.json"
    derived.write_text(json.dumps({"status": "ocr_unverified",
                                    "source_sha256": "0" * 64, "text": "X" * 100}))
    with pytest.raises(ValueError):
        enqueue_ocr(original_pdf=original, ocr_json=derived,
                    queue_dir=tmp_path / "queue", registry_number="32616280467")


def test_empty_pending_packet_is_skipped(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    (queue / "123.json").write_text(json.dumps({
        "schema_version": "pq-review-queue/1", "state": "pending_review",
        "packet": {"registry_number": "32616280467",
                   "documents": [{"text": "\f\n "}]}}))
    result = next_packet(queue_dir=queue)
    assert result["status"] == "empty"
    assert result["pending_unreadable"] == 1
