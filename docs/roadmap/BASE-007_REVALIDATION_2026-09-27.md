# BASE-007 EIS SOAP contour revalidation

Date: 2026-09-27  
Task: `BASE-007-REVALIDATION-001`  
Base: `189799ce4cc44a4e83e75169d689613bd14b55bf`

## Result

The historical “basic contour ready” statement remains supported for the repository implementation. Current main contains a machine-readable EIS SOAP/getDocsIP adapter, controlled settings, fail-closed trust primitives, sanitized diagnostics and mocked unit coverage.

The historical item is not complete. Repository evidence does not establish a current credentialed production smoke, active endpoint/token/certificate/direct-route/allowlist acceptance or a dedicated operator runbook. The legacy `int44` search path remains separate and is not treated as the primary successful route.

## Evidence matrix

| Capability | Current evidence | Reconciliation |
|---|---|---|
| Registry-number document acquisition | `src/tender_research/eis_real_loader.py` calls `get_docs_by_reestr_number` and classifies no-data/auth/token/connection failures. | Implemented in repository. |
| getDocsIP request/response path | `zakupki_soap_client.py` builds `getDocsByReestrNumberRequest`, posts to the individual endpoint and parses the bounded archive result. | Implemented in repository. |
| Token handling | `settings.py` reads environment configuration; diagnostics mask tokens and sanitize request/error artifacts. | Implemented; no secret inspected. |
| Host and route boundary | Settings declare EIS allowed hosts, direct-route defaults and proxy controls; archive download rejects non-allowlisted hosts. | Implemented in repository. |
| Certificate/trust boundary | Shared trust code validates pinned/custom authorities, uses verified system trust and fails closed on invalid policy. | Implemented in repository. |
| Deterministic tests | `tests/tender_research/test_eis_real_loader.py` covers mocked success/failure/configuration paths. | Unit evidence only; not live acceptance. |
| Current production smoke | No attributable current redacted live result was established by this inspection. | Missing; HUMAN/operator evidence required. |
| Operational runbook | No dedicated canonical EIS SOAP operator runbook was established by the inspected evidence. | Residual gap. |
| ARV-014 dependency | Historical trust code exists; external allowlist/direct-route acceptance remains unverified. | Dependency remains open/gated. |

## Bounded successor candidate

Candidate only; **not admitted**:

`BASE-007-EIS-SOAP-OPERATIONS-EVIDENCE-001 — Controlled EIS SOAP smoke and operator runbook evidence`

Traceable scope:

1. document non-secret configuration, fail-closed preflight, method selection, sanitized diagnostics and recovery steps;
2. only under separately confirmed HUMAN/operator authority, run a bounded read-only `getDocsByReestrNumber` smoke with existing approved credentials and network route;
3. store only redacted status/method/timestamp evidence—never tokens, private keys, certificate material or procurement documents;
4. do not request allowlisting, bypass Anti-DDoS, change production, or treat `int44` as the primary route.

## Boundaries

No EIS endpoint was called, no token/private key/certificate store was accessed, no protection was bypassed, no allowlist request or external message was sent, and no production or procurement action occurred.
