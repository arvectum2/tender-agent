import json

from src.modules.market_intelligence.pq_arc_batch import begin, complete


def test_batch_lease_and_review(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    runtime = tmp_path / "runtime"
    item = {"schema_version": "pq-review-queue/1", "id": "123-abc",
            "state": "pending_review", "review": None,
            "packet": {"registry_number": "123", "documents": [{
                "filename": "doc.txt", "sha256": "a" * 64,
                "text": "поставка автомобиля для аварийно-спасательного формирования"}]}}
    (queue / "123-abc.json").write_text(json.dumps(item))
    first = begin(queue_dir=queue, runtime_dir=runtime)
    assert first["status"] == "pending"
    assert begin(queue_dir=queue, runtime_dir=runtime)["status"] == "busy"
    decision = {"registry_number": "123", "classification": "irrelevant",
                "evidence": [{"sha256": "a" * 64,
                              "quote": "поставка автомобиля для аварийно-спасательного формирования"}],
                "reasoning": "Vehicle, not power quality equipment"}
    outcome = complete(queue_dir=queue, runtime_dir=runtime,
                       owner=first["lease_owner"], identity=first["id"], review=decision)
    assert outcome["status"] == "reviewed"
    assert begin(queue_dir=queue, runtime_dir=runtime)["status"] == "empty"
