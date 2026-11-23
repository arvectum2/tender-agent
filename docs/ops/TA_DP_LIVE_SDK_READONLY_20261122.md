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

## Protected main completion and independent DP SLO blocker

PR #714 exact head 55c1268230513e62acc3cca9b5cfdd804107c423
passed 10/10 protected GitHub CI and merged as
d1de9c398d30fff738e89be1513c7caa4db319f6.
The bounded SDK read-only source/contract task is COMPLETED; no production
release was performed or authorized.

A separate authenticated local-only GET to /v1/support/readiness revealed
the actual DP v0.6.0 operational gate: overall RED. The last 256 ingest
latency observations have p95 18,887 ms versus the explicit server
OPERATION_SLOS ingest threshold 10,000 ms (7,989 ingest requests since
process start, zero reported errors). Search and process statuses were
GREEN at that observation; five other operation types lacked enough
samples for independent quality claims.

Immutable private 0600 source-safe readiness receipt SHA256:
1b3fedc89a25e348e6bdfb0c7f47567e447f20687ec0336c746728911284310d.
No raw document texts, collection identities, secrets or production
payloads entered the repository. This establishes an actual latency
readiness failure, but does not identify its root cause. The separate
Data Platform issue arvectum2/data-platform#133 contains a synthetic,
source-preserving investigation plan and a possible event-loop blocking
hypothesis requiring measurement.

Do not equate three successful read-only SDK requests with production
readiness. The Core runtime release remains BLOCKED on representative
ingest p95 <=10s, sustained DP quality, independently accepted real
Gemma source evidence and an exact Owner release/rollback decision.
