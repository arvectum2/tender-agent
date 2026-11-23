"""Network-free adversarial tests for locally authenticated DP consumer SDK GET."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from scripts.ops import audit_dp_live_sdk_readonly as m


def _private_env(tmp_path: Path, contents: str):
    path = tmp_path / "runtime.env"
    path.write_text(contents)
    path.chmod(0o600)
    return path


def _mock_server(monkeypatch, *, contract="1.0.0", count=2, anon=401, coll_status=200):
    actual_client = httpx.Client
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, request.url.host))
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "service": "arvectum-data"})
        if request.url.path == "/v1/contract":
            return httpx.Response(200, json={
                "name": "arvectum-data-consumer",
                "version": contract,
                "capabilities": [],
            })
        if request.url.path == "/v1/collections":
            return httpx.Response(
                coll_status, json=[{"collection_id": str(i)} for i in range(count)]
            )
        return httpx.Response(404, json={"detail": "missing"})

    transport = httpx.MockTransport(handler)
    def mocked_client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        assert kwargs["base_url"] == m.ALLOWED_BASE
        return actual_client(transport=transport, **kwargs)

    def mocked_anonymous(*_args, **kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return SimpleNamespace(status_code=anon)

    monkeypatch.setattr(m.httpx, "Client", mocked_client)
    monkeypatch.setattr(m.httpx, "get", mocked_anonymous)
    return requests


def test_local_credentials_only_0600_and_not_in_output(tmp_path, monkeypatch):
    env = _private_env(tmp_path, "ARVECTUM_DATA_INTERNAL_API_KEY='synthetic-secret-xyz'\n")
    assert m.load_local_key(env) == "synthetic-secret-xyz"
    requests = _mock_server(monkeypatch)
    result = m.probe_once(m.ALLOWED_BASE, m.load_local_key(env))
    assert result["collections_read_count"] == 2
    assert result["consumer_contract_major"] == 1
    assert result["anonymous_collections_http"] == 401
    assert len(requests) == 3
    assert all(method == "GET" and host == "127.0.0.1" for method, _, host in requests)
    assert "synthetic-secret-xyz" not in json.dumps(result)


def test_env_missing_key_fail_closed(tmp_path):
    env = _private_env(tmp_path, "OTHER_VAR=test\n")
    with pytest.raises(m.ProbeBlocked, match="missing_or_ambiguous"):
        m.load_local_key(env)


def test_env_duplicate_key_fail_closed(tmp_path):
    env = _private_env(tmp_path, "ARVECTUM_DATA_INTERNAL_API_KEY=a\nARVECTUM_DATA_INTERNAL_API_KEY=b\n")
    with pytest.raises(m.ProbeBlocked, match="missing_or_ambiguous"):
        m.load_local_key(env)


def test_env_wrong_mode_fail_closed(tmp_path):
    env = _private_env(tmp_path, "ARVECTUM_DATA_INTERNAL_API_KEY=test\n")
    env.chmod(0o644)
    with pytest.raises(m.ProbeBlocked, match="unsafe_private"):
        m.load_local_key(env)


def test_env_symlink_fail_closed(tmp_path):
    env = _private_env(tmp_path, "ARVECTUM_DATA_INTERNAL_API_KEY=test\n")
    link = tmp_path / "symlink.env"
    link.symlink_to(env)
    with pytest.raises(m.ProbeBlocked, match="unsafe_private"):
        m.load_local_key(link)


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8094",
    "http://localhost:8094",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8094@external.example",
    "http://192.168.1.1:8094",
])
def test_noncanonical_host_never_admitted(url):
    with pytest.raises(m.ProbeBlocked, match="non_loopback"):
        m.validate_base(url)


def test_wrong_consumer_contract_blocked(monkeypatch):
    _mock_server(monkeypatch, contract="2.0.0")
    with pytest.raises(m.ProbeBlocked, match="sdk_contract"):
        m.probe_once(m.ALLOWED_BASE, "fake-secret")


def test_sdk_error_503_safe_classification(monkeypatch):
    _mock_server(monkeypatch, coll_status=503)
    with pytest.raises(m.ProbeBlocked, match="sdk_http_503") as error:
        m.probe_once(m.ALLOWED_BASE, "fake-secret")
    assert "fake-secret" not in str(error.value)


def test_anonymous_collections_should_be_401(monkeypatch):
    _mock_server(monkeypatch, anon=200)
    with pytest.raises(m.ProbeBlocked, match="anonymous_access_not_rejected"):
        m.probe_once(m.ALLOWED_BASE, "fake-secret")


def test_malformed_collection_payload_blocked(monkeypatch):
    # Return an object instead of a collection list, without touching the network.
    actual_client = httpx.Client
    monkeypatch.setattr(
        m.httpx, "get", lambda *_args, **_kwargs: SimpleNamespace(status_code=401),
    )

    def handler(request):
        match request.url.path:
            case "/health":
                return httpx.Response(200, json={"status": "ok", "service": "arvectum-data"})
            case "/v1/contract":
                return httpx.Response(200, json={"version": "1.0.0", "capabilities": []})
            case _:
                return httpx.Response(200, json={"collections": ["redacted"]})

    monkeypatch.setattr(
        m.httpx, "Client",
        lambda **kwargs: actual_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(m.ProbeBlocked, match="invalid_collections_schema"):
        m.probe_once(m.ALLOWED_BASE, "fake-secret")


def test_version_mismatch_blocks_before_requests(monkeypatch):
    monkeypatch.setattr(m, "version", lambda _name: "0.3.0")
    monkeypatch.setattr(m, "probe_once", lambda *_a, **_k: pytest.fail("should not call HTTP"))
    with pytest.raises(m.ProbeBlocked, match="sdk_consumer_version_mismatch"):
        m.audit(m.ALLOWED_BASE, "fake-secret")


def test_short_bounded_audit_does_not_claim_sustained_reliability(monkeypatch):
    monkeypatch.setattr(m, "version", lambda _name: m.SDK_EXPECTED)
    calls = []

    def probe(_base, _key):
        calls.append(1)
        return {"collections_read_count": 73, "elapsed_ms": 12.5}

    monkeypatch.setattr(m, "probe_once", probe)
    monkeypatch.setattr(m.time, "sleep", lambda _t: None)
    result = m.audit(m.ALLOWED_BASE, "fake-secret", samples=3)
    assert len(calls) == 3
    assert result["samples"] == 3
    assert result["collection_count"] == 73
    assert result["sdk_package_version"] == m.SDK_EXPECTED
    assert result["sustained_multi_hour_reliability_proven"] is False
    assert result["owner_runtime_release_approved"] is False
    assert result["production_deployed"] is False
    assert result["probe_http_methods"] == ["GET"]
    assert "fake-secret" not in json.dumps(result)


def test_collection_counts_changing_blocks_snapshot(monkeypatch):
    monkeypatch.setattr(m, "version", lambda _name: m.SDK_EXPECTED)
    results = iter([{"collections_read_count": 72, "elapsed_ms": 1},
                    {"collections_read_count": 73, "elapsed_ms": 1}])
    monkeypatch.setattr(m, "probe_once", lambda *_args: next(results))
    monkeypatch.setattr(m.time, "sleep", lambda _t: None)
    with pytest.raises(m.ProbeBlocked, match="collection_count_changed"):
        m.audit(m.ALLOWED_BASE, "fake-secret", samples=2)


def test_out_of_bounds_sampling_rejected_without_http(monkeypatch):
    monkeypatch.setattr(m, "probe_once", lambda *_args: pytest.fail("unexpected HTTP"))
    for samples, interval in ((0, 0), (6, 0), (1, -1), (1, 501)):
        with pytest.raises(m.ProbeBlocked, match="invalid_bounded"):
            m.audit(m.ALLOWED_BASE, "fake-secret", samples=samples, interval_ms=interval)


def test_proof_is_0600_immutable_and_source_free(tmp_path):
    path = tmp_path / "private.json"
    proof = {
        "status": "PASS_BOUNDED_LOCAL_DP_SDK_GET_NOT_PRODUCTION_RELEASE",
        "credential_in_receipt": False,
        "collection_ids_in_receipt": False,
    }
    m.private_proof_once(path, proof)
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == proof
    with pytest.raises(m.ProbeBlocked, match="unsafe_or_existing"):
        m.private_proof_once(path, {"override": True})
