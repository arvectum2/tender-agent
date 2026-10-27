"""Queue deduplication and immutable source-backed review."""
import pytest

from src.modules.market_intelligence.pq_review_queue import enqueue, accept


def test_queue_replay_and_review(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "document.txt").write_text("поставка автомобиля для аварийно-спасательного формирования")
    ontology = tmp_path / "ontology.yaml"
    ontology.write_text("families:\n  - id: ukrm\n    positive: ['УКРМ']\n")
    args = dict(source_dir=source, ontology=ontology, registry_number="32313113128",
                queue_dir=tmp_path / "queue")
    item = enqueue(**args)
    assert enqueue(**args)["id"] == item["id"]
    sha = item["packet"]["documents"][0]["sha256"]
    review = {"registry_number": "32313113128", "classification": "irrelevant",
              "evidence": [{"sha256": sha, "quote": "поставка автомобиля для аварийно-спасательного формирования"}]}
    assert accept(queue_dir=args["queue_dir"], identity=item["id"], review=review)["state"] == "reviewed"
    assert accept(queue_dir=args["queue_dir"], identity=item["id"], review=review)["state"] == "reviewed"
    changed = {**review, "classification": "relevant"}
    with pytest.raises(ValueError, match="Immutable"):
        accept(queue_dir=args["queue_dir"], identity=item["id"], review=changed)
