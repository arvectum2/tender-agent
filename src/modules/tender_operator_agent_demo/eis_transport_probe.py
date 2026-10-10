"""Fast, read-only, proxy-free TLS preflight for the official EIS SOAP endpoint.

The probe only opens a TCP/TLS socket. It never sends a SOAP envelope,
uses the operator token, writes original data, or follows an HTTP redirect.
"""

from __future__ import annotations

import socket
import ssl
import time
from dataclasses import asdict, dataclass
from collections.abc import Callable
from urllib.parse import urlparse

from src.shared.network.http_client import create_urllib_context

_SUPPORTED_PROBE_HOSTS = {"int.zakupki.gov.ru", "zakupki.gov.ru"}


@dataclass(frozen=True)
class EisTlsProbeResult:
    endpoint_host: str
    route: str
    stage: str
    status: str
    elapsed_ms: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def probe_eis_tls(
    url: str,
    *,
    timeout_seconds: float = 3.0,
    connection_factory: Callable = socket.create_connection,
    context_factory: Callable = create_urllib_context,
) -> EisTlsProbeResult:
    """Return a bounded stage-specific classification without proxy mediation.

    Direct socket.create_connection intentionally ignores HTTP_PROXY, HTTPS_PROXY,
    ALL_PROXY, NO_PROXY and macOS PAC; this must not be changed into urlopen().
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _SUPPORTED_PROBE_HOSTS or (
        parsed.port not in {None, 443}
    ):
        raise ValueError("Only exact official HTTPS EIS hosts on port 443 are accepted")
    if not 0 < timeout_seconds <= 10:
        raise ValueError("TLS preflight timeout must be between 0 and 10 seconds")

    started = time.monotonic()
    stage = "tcp"
    try:
        # The application and probe share the same authenticated OS trust policy,
        # but only the actual application SOAP POST can prove an API operation.
        context, _policy_bypass = context_factory(url)
        with connection_factory((host, 443), timeout=timeout_seconds) as raw:
            stage = "tls"
            raw.settimeout(timeout_seconds)
            with context.wrap_socket(raw, server_hostname=host):
                stage = "ready"
                status = "verified_tls"
    except socket.gaierror:
        status = "dns_failure"
    except ssl.SSLCertVerificationError:
        status = "certificate_rejected"
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        status = "connection_reset_during_" + stage
    except TimeoutError:
        status = "timeout_during_" + stage
    except ssl.SSLError:
        status = "tls_handshake_failed"
    except OSError:
        status = "network_failure_during_" + stage
    except RuntimeError:
        status = "tls_trust_context_unavailable"

    return EisTlsProbeResult(
        endpoint_host=host,
        route="direct_socket_no_proxy",
        stage=stage,
        status=status,
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )
