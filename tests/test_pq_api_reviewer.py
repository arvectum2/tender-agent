"""OpenAI reviewer must not make network calls without explicit execute/credential."""
import json

from src.modules.market_intelligence.pq_api_reviewer import review_pending


def test_preflight_and_no_credential(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    queue = tmp_path / "review.json"
    queue.write_text(json.dumps({
        "id": "test", "state": "pending_review",
        "packet": {"registry_number": "32313113128", "documents": [
            {"sha256": "a" * 64, "filename": "doc.txt", "text": "поставка автомобиля для аварийно-спасательного формирования"}]},
        "review": None,
    }))
    assert review_pending(queue_path=queue, model="gpt-5", execute=False)["status"] == "ready_no_network"
    assert review_pending(queue_path=queue, model="gpt-5", execute=True)["status"] == "blocked_missing_openai_api_key"
    assert json.loads(queue.read_text())["state"] == "pending_review"
