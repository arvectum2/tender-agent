from src.modules.market_intelligence.pq_run_lease import acquire, inspect, renew, release


def test_owner_lease_and_heartbeat(tmp_path):
    path = tmp_path / "lease"
    lease = acquire(path, now=1000, ttl_seconds=120)
    assert lease is not None
    assert acquire(path, now=1001, ttl_seconds=120) is None
    assert inspect(path, now=1100)["status"] == "held"
    assert renew(lease, now=1100, ttl_seconds=120)
    assert inspect(path, now=1200)["status"] == "held"
    assert inspect(path, now=1221)["status"] == "expired"
    assert not renew(lease, now=1221, ttl_seconds=120)
    assert release(lease)
    assert inspect(path)["status"] == "free"


def test_unreadable_requires_reconciliation(tmp_path):
    path = tmp_path / "lease"
    path.mkdir()
    assert inspect(path)["requires_reconciliation"]
    assert acquire(path) is None
