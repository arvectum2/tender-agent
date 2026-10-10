"""Safe direct RU-network EIS SOAP preflight.

Examples:
    python scripts/ops/check_eis_direct.py
    python scripts/ops/check_eis_direct.py --soap 0352300080626000109

By default no token or SOAP payload is sent. A live GET/POST is not confused
with a successful TLS-only preflight.
"""

from __future__ import annotations

import argparse
import json

from src.modules.tender_operator_agent_demo.eis_transport_probe import probe_eis_tls
from src.modules.tender_operator_agent_demo.settings import (
    DEFAULT_INDIVIDUAL_BASE_URL,
    get_zakupki_soap_settings,
)

_PUBLIC_URL = "https://zakupki.gov.ru/"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only EIS direct TLS diagnostic")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--soap", metavar="REESTR_NUMBER", help="Opt-in actual read-only getDocsIP POST")
    args = parser.parse_args()

    settings = get_zakupki_soap_settings()
    url = settings.individual_base_url or DEFAULT_INDIVIDUAL_BASE_URL
    route_required = settings.require_direct_ru_route and settings.disable_proxy_for_eis
    public_probe = probe_eis_tls(_PUBLIC_URL, timeout_seconds=args.timeout).to_dict()
    try:
        integration_probe = probe_eis_tls(url, timeout_seconds=args.timeout).to_dict()
    except ValueError:
        integration_probe = {"status": "invalid_official_endpoint", "route": "not_attempted"}
    results = {
        "contract": "eis-direct-transport-preflight-v1",
        "soap_configured": settings.configured,
        "direct_route_configured": route_required,
        "public_site": public_probe,
        "integration": integration_probe,
        "note": "Direct TCP/TLS only; country check performed separately; token never printed.",
    }
    ready = results["integration"]["status"] == "verified_tls" and route_required
    if args.soap:
        if not ready:
            results["soap"] = {"status": "skipped", "reason": "integration_tls_unavailable"}
        elif not settings.configured:
            results["soap"] = {"status": "skipped", "reason": "token_not_configured"}
        else:
            from src.modules.tender_operator_agent_demo.zakupki_soap_client import (
                ZakupkiSoapClient,
            )

            try:
                result = ZakupkiSoapClient(
                    settings, runtime_status_enabled=False
                ).get_docs_by_reestr_number(args.soap)
                results["soap"] = {"status": result.status}
            except RuntimeError:
                results["soap"] = {"status": "error", "reason": "soap_request_failed"}
    print(json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if ready and (not args.soap or results["soap"]["status"] == "completed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
