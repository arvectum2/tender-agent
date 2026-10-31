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


def test_next_packet_skips_already_reviewed_same_source_sha(tmp_path):
    def item(identity, state, sha, registry="32414141662"):
        return {"schema_version": "pq-review-queue/1", "id": identity,
                "state": state, "packet": {"registry_number": registry,
                "documents": [{"filename": "a.docx", "sha256": sha,
                               "text": "Technical equipment at 110 kV"}]},
                "review": {"classification": "irrelevant"} if state == "reviewed" else None}

    (tmp_path / "a-reviewed.json").write_text(json.dumps(
        item("a-reviewed", "reviewed", "a" * 64)))
    (tmp_path / "b-duplicate.json").write_text(json.dumps(
        item("b-duplicate", "pending_review", "a" * 64)))
    result = next_packet(queue_dir=tmp_path)
    assert result["status"] == "empty"
    assert result["pending_exact_sha_duplicates_skipped"] == 1
    (tmp_path / "c-new-source.json").write_text(json.dumps(
        item("c-new-source", "pending_review", "b" * 64)))
    result = next_packet(queue_dir=tmp_path)
    assert result["status"] == "pending"
    assert result["id"] == "c-new-source"
    assert json.loads((tmp_path / "b-duplicate.json").read_text())["state"] == "pending_review"
