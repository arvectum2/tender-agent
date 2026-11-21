import pytest

from scripts.ops.recover_daily_index import identity_digest, journal, pending_journal


def test_identity_digest_has_stable_order_and_binds_release():
    assert identity_digest({"a": 1, "b": 2}) == identity_digest({"b": 2, "a": 1})
    assert identity_digest({"release": "1"}) != identity_digest({"release": "2"})


def test_successful_batch_can_resume(tmp_path):
    root = tmp_path.resolve() / "receipts"
    with journal(root, "123", {"identity_sha256": "a" * 64}) as record:
        record("ingest_requested", {"chunk_id": "c1"})
        record("ingest_response", {"chunk_id": "c1"})
        record("verified_batch", {"remaining": 1})
    pending_journal(root, "123")
    assert len(list(root.glob("123-*.jsonl"))) == 1
    with journal(root, "123", {"identity_sha256": "a" * 64}) as record:
        record("verified_batch", {"remaining": 0})
    assert len(list(root.glob("123-*.jsonl"))) == 2


def test_interrupted_attempt_refuses_automatic_replay(tmp_path):
    root = tmp_path.resolve() / "receipts"
    with pytest.raises(TimeoutError), journal(root, "123", {}) as record:
        record("ingest_requested", {"chunk_id": "c1"})
        raise TimeoutError
    with (
        pytest.raises(RuntimeError, match="independent reconciliation"),
        journal(root, "123", {}),
    ):
        pytest.fail("ambiguous operation was repeated")


def test_success_without_verification_record_remains_unresolved(tmp_path):
    root = tmp_path.resolve() / "receipts"
    with journal(root, "123", {}) as record:
        record("ingest_response", {"chunk_id": "c1"})
    with pytest.raises(RuntimeError):
        pending_journal(root, "123")
