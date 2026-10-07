# ARV-014 repository revalidation — 2026-10-07

This is the standard bounded `REVALIDATION` slice materialized by the active Owner continuation directive for historical `ARV-014` in `PRODUCTION-RUNTIME`. It is repository-only and creates no provider, network, credential, production, procurement, commercial, or external effect.

## Evidence checked

- Canonical continuation order and the current ARV-014 roadmap record at base `a143d218b1c039ab4197a3f61ab7215182f7ccd9`.
- Completed repository revalidations `ARV-011-REVALIDATION-001` and `ARV-012-REVALIDATION-001`; neither proves a permanent VPS IP, completed migration, or external platform allowlist.
- `docs/operations/MACMINI_PUBLIC_EIS_TLS_PATH.md`, `src/shared/network/etp_trust.py`, and the public 44-FZ transport path.
- Deterministic trust and routing regressions in `tests/test_etp_trust.py` and `tests/test_public_eis_transport_policy.py`.
- Current repository search for ARV-014, allowlist, Anti-DDoS, permanent-IP, and ETP trust evidence.

## Reconciliation

The technical trust contour described by the historical ARV-014 baseline is present and fail-closed:

- certificate and hostname verification remain required;
- TLS 1.2 is the minimum;
- system and pinned/custom authority paths are explicit;
- host matching is boundary-safe;
- the public EIS direct-route exception is restricted to the explicit EIS host allowlist and does not disable TLS verification.

The historical external result is **not proven satisfied**. Repository evidence does not establish a permanent VPS IP, EIS/ETP provider-side allowlisting, an attributable Anti-DDoS configuration, or an accepted IP-change procedure. The predecessor ARV-011/ARV-012 revalidations explicitly preserve that external infrastructure state as unproven.

ARV-014 is therefore reconciled as `revalidated_residual_gap`: the repository-owned trust foundation is verified, while the external allowlist/Anti-DDoS result remains gated by a future permanent-IP decision and separately authorized provider/network work. No successor implementation is admitted by this slice.

## Boundary

No production endpoint, firewall, provider account, Anti-DDoS service, credential, allowlist, DNS record, procurement platform, benchmark truth, or Company/Product authority was read or mutated. External allowlist requests and production-network changes remain REVIEW/HUMAN/OWNER-gated.
