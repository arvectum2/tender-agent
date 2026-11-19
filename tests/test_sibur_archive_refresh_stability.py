"""An isolated read-only refresh timeout cannot starve safe member indexing."""
import hashlib
from unittest.mock import Mock
import pytest
from scripts.research import autonomous_runner as mod


def runner(tmp_path):
    r=mod.Runner.__new__(mod.Runner)
    r.archive_refresh_retry_at=0
    r.state={"lanes":{"sibur":{"archive_synced_count":1,"index_inflight":False}}}
    r.refresh_archive_bridge=Mock()
    r.local_index=Mock(return_value={"sha":{}})
    r.reconcile_index=Mock()
    r.update=Mock()
    p=tmp_path/"bridge.json"
    p.write_bytes(b"active")
    return r,p,hashlib.sha256(p.read_bytes()).hexdigest()


def test_timeout_reconciles_and_defers_optional_scan(tmp_path,monkeypatch):
    r,p,h=runner(tmp_path)
    monkeypatch.setattr(mod.time,"monotonic",lambda:100)
    r.refresh_archive_bridge.side_effect=mod.Blocked("refresh_sibur_archive_index: timeout; reconcile before retry")
    assert r.refresh_archive_when_due("sibur",p,h) is None
    r.reconcile_index.assert_called_once_with({"sha":{}})
    assert r.archive_refresh_retry_at==1000
    assert r.refresh_archive_when_due("sibur",p,h) is None
    assert r.refresh_archive_bridge.call_count==1


@pytest.mark.parametrize("issue",["digest","inflight","count","other_error"])
def test_unsafe_or_unknown_failure_not_deferred(tmp_path,issue):
    r,p,h=runner(tmp_path)
    msg="refresh_sibur_archive_index: timeout; reconcile before retry"
    if issue=="digest":p.write_bytes(b"changed")
    elif issue=="inflight":r.state["lanes"]["sibur"]["index_inflight"]=True
    elif issue=="count":r.state["lanes"]["sibur"]["archive_synced_count"]=2
    else:msg="archive refresh baseline changed"
    r.refresh_archive_bridge.side_effect=mod.Blocked(msg)
    with pytest.raises(mod.Blocked):r.refresh_archive_when_due("sibur",p,h)
    r.reconcile_index.assert_not_called()


def test_empty_scan_has_cooldown_but_new_ready_is_returned(tmp_path,monkeypatch):
    r,p,h=runner(tmp_path)
    clock=[100]
    monkeypatch.setattr(mod.time,"monotonic",lambda:clock[0])
    r.refresh_archive_bridge.return_value=None
    assert r.refresh_archive_when_due("sibur",p,h) is None
    assert r.archive_refresh_retry_at==1000
    clock[0]=1001
    r.refresh_archive_bridge.return_value=("new",["row"])
    assert r.refresh_archive_when_due("sibur",p,h)==("new",["row"])
    assert r.archive_refresh_retry_at==0
