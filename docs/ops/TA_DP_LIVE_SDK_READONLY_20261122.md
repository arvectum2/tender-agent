# 22 November 2026 — Data Platform authenticated SDK/HTTP short probe

Scope: issue-free, bounded read-only source and credential parity follow-up
for the independent Core runtime release checkpoint. **NOT** approval to
deploy the new Core/PRICE01 runtime, turn on Gemma, or declare a
long-duration Data Platform SLO complete.

## Live read-only evidence, Mac mini

- Actual Tender Agent backend on 127.0.0.1:8001/health returned HTTP 200.
- Actual Data Platform on 127.0.0.1:8094/health returned HTTP 200,
  service=arvectum-data, version 0.6.0.
- Installed active Tender Agent release venv consumes
  arvectum-data-client 0.4.0, the exact SDK version pinned in protected
  Tender Agent main; the 14-Nov old 0.3.0 mismatch is no longer current.
- Three separately authenticated SDK read-only rounds of /health,
  /v1/contract and /v1/collections succeeded. The v1 consumer contract
  is compatible, the collection list contained exactly 73 items in each
  round, and anonymous GET /v1/collections was rejected HTTP 401.
- Final proof run used an explicit httpx transport with trust_env=False,
  follow_redirects=False, fixed http://127.0.0.1:8094, 3-second
  request timeout and 3 bounded rounds (200 ms apart). Each transport
  request was GET; no APIs that modify collections, documents, indices,
  source state, bids, memory or billing were called.
- The final proof stores only safe aggregate counts, versions, response
  class and measured elapsed times. Credential and collection IDs never
  enter its JSON or the repository.
- Independent immutable mode 0600 private proof SHA256:
  55b7f94f50391eff7d4f920accbf07620a29ece913254826eff2cdf40ca9ac80.
  This SHA identifies the saved aggregate receipt, not the credential.
- DP app middleware source inspection confirms that its database-backed
  usage event path is not mapped to these GET routes; the probe still
  increments ordinary in-memory HTTP request counters.

## Reproducibility and negative gates

scripts/ops/audit_dp_live_sdk_readonly.py accepts only the literal local
host http://127.0.0.1:8094, loads the existing 0600 runtime env
credential locally, runs three short authenticated SDK GET cycles with an
anonymous authorization negative-control, and can emit a no-overwrite
0600 private receipt once. All credential values and source contents
stay outside git. Invalid host, insecure/symlinked/ambiguous credential,
wrong SDK version/consumer contract, HTTP 503, malformed list response,
unexpected anonymous admission, drift in collection count or excessive
sampling are rejected without promoting results.

## Release remains independently blocked

A few successful local GETs prove a **point-in-time read contract**,
not sustained HTTP/SDK reliability across deployment, no guaranteed
latency under load, no live data search/retrieval correctness, and no
independent real source-grounded Gemma acceptance.

Keep TA-CORE-RUNTIME-RELEASE-20261122 BLOCKED for longer observation,
independent Gemma acceptance, Owner approval of exact staging/image
and a separately authorized production cutover/rollback. The upstream
no-EIS-blind-retry and seven-day-PITR gates stay separate; no owner release
authorization is inferred from this inspection.
