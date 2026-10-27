"""ARC handoff returns bounded, source-identified excerpts only."""
import json

from src.modules.market_intelligence.pq_arc_chat import next_packet


def test_next_packet(tmp_path):
    assert next_packet(queue_dir=tmp_path)["status"] == "empty"
    packet = {"schema_version": "pq-review-queue/1", "id": "test-abc",
              "state": "pending_review", "packet": {
                  "registry_number": "32313113128", "documents": [
                      {"filename": "source.txt", "sha256": "a" * 64,
                       "text": "A" * 2000}]}}
    (tmp_path / "test.json").write_text(json.dumps(packet))
    result = next_packet(queue_dir=tmp_path, max_chars=1000)
    assert result["status"] == "pending"
    assert result["reviewer"] == "current_chatgpt_conversation_via_arc"
    assert len(result["documents"][0]["text"]) == 1000
    assert result["documents"][0]["text_excerpt_only"]
