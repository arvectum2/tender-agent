"""No credential or HTTP proxy is used by the direct EIS TLS probe."""

import ssl
from unittest.mock import MagicMock

import pytest

from src.modules.tender_operator_agent_demo.eis_transport_probe import probe_eis_tls
from src.modules.tender_operator_agent_demo.settings import (
    DEFAULT_INDIVIDUAL_BASE_URL,
    DEFAULT_LEGACY_BASE_URL,
)


def _connector(result=None, error=None):
    def connect(address, *, timeout):
        assert address == ("int.zakupki.gov.ru", 443)
        assert timeout == 2
        if error:
            raise error
        return result

    return connect


def test_direct_probe_never_consults_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://untrusted-proxy.example:8000")
    monkeypatch.setenv("ALL_PROXY", "http://untrusted-proxy.example:8000")
    raw = MagicMock()
    raw.__enter__.return_value = raw
    context = MagicMock()
    tls = MagicMock()
    tls.__enter__.return_value = tls
    context.wrap_socket.return_value = tls
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(raw),
        context_factory=lambda _url: (context, True),
    )
    assert result.route == "direct_socket_no_proxy"
    assert result.status == "verified_tls"
    context.wrap_socket.assert_called_once_with(raw, server_hostname="int.zakupki.gov.ru")


def test_remote_reset_is_classified_at_tcp_stage():
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(error=ConnectionResetError(54, "reset")),
        context_factory=lambda _url: (MagicMock(), True),
    )
    assert result.status == "connection_reset_during_tcp"


def test_remote_reset_is_classified_at_tls_stage():
    raw = MagicMock()
    raw.__enter__.return_value = raw
    ctx = MagicMock()
    ctx.wrap_socket.side_effect = ConnectionResetError(54, "reset")
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(raw),
        context_factory=lambda _url: (ctx, True),
    )
    assert result.status == "connection_reset_during_tls"


def test_certificate_verification_is_never_suppressed():
    raw = MagicMock()
    raw.__enter__.return_value = raw
    ctx = MagicMock()
    ctx.wrap_socket.side_effect = ssl.SSLCertVerificationError("untrusted")
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(raw),
        context_factory=lambda _url: (ctx, True),
    )
    assert result.status == "certificate_rejected"


@pytest.mark.parametrize("url", [
    "http://int.zakupki.gov.ru",
    "https://example.com/",
    "https://int.zakupki.gov.ru:8443/",
    "https://attacker.zakupki.gov.ru/",
])
def test_probe_rejects_unapproved_destinations(url):
    with pytest.raises(ValueError):
        probe_eis_tls(url)


def test_legacy_endpoint_default_uses_current_official_domain():
    assert DEFAULT_LEGACY_BASE_URL.startswith(
        "https://int.zakupki.gov.ru/eis-integration/"
    )


def test_probe_enforces_short_maximum_timeout():
    with pytest.raises(ValueError):
        probe_eis_tls(DEFAULT_INDIVIDUAL_BASE_URL, timeout_seconds=30)


def test_tcp_timeout_classified_without_fake_success():
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(error=TimeoutError("slow")),
        context_factory=lambda _url: (MagicMock(), False),
    )
    assert result.status == "timeout_during_tcp"


def test_trust_store_failure_does_not_disable_verification():
    result = probe_eis_tls(
        DEFAULT_INDIVIDUAL_BASE_URL,
        timeout_seconds=2,
        connection_factory=_connector(),
        context_factory=lambda _url: (_ for _ in ()).throw(RuntimeError("CA not ready")),
    )
    assert result.status == "tls_trust_context_unavailable"


def test_direct_cli_skips_soap_if_tls_unavailable(monkeypatch, capsys):
    import json
    import sys

    from scripts.ops import check_eis_direct as cli
    from src.modules.tender_operator_agent_demo.eis_transport_probe import EisTlsProbeResult
    from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings

    token = "private-token-must-never-appear"
    monkeypatch.setattr(cli, "get_zakupki_soap_settings", lambda: ZakupkiSoapSettings(
        enabled=True, token=token
    ))
    def fake_probe(url, **_kwargs):
        status = "verified_tls" if "int." not in url else "connection_reset_during_tls"
        return EisTlsProbeResult(
            endpoint_host="int.zakupki.gov.ru" if "int." in url else "zakupki.gov.ru",
            route="direct_socket_no_proxy",
            stage="tls",
            status=status,
            elapsed_ms=19,
        )
    monkeypatch.setattr(cli, "probe_eis_tls", fake_probe)
    monkeypatch.setattr(sys, "argv", ["check_eis_direct.py", "--soap", "0352300080626000109"])
    assert cli.main() == 2
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["soap"] == {"status": "skipped", "reason": "integration_tls_unavailable"}
    assert token not in output


def test_direct_cli_rejects_nonofficial_config_without_network(monkeypatch, capsys):
    import json
    import sys

    from scripts.ops import check_eis_direct as cli
    from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings

    monkeypatch.setattr(cli, "get_zakupki_soap_settings", lambda: ZakupkiSoapSettings(
        enabled=True, token="secret", individual_base_url="https://example.com/"
    ))
    monkeypatch.setattr(cli, "probe_eis_tls", lambda url, **_kwargs: (
        (_ for _ in ()).throw(ValueError("not official")) if "example.com" in url
        else MagicMock(to_dict=lambda: {"status": "verified_tls"})
    ))
    monkeypatch.setattr(sys, "argv", ["check_eis_direct.py"])
    assert cli.main() == 2
    assert json.loads(capsys.readouterr().out)["integration"]["status"] == (
        "invalid_official_endpoint"
    )
