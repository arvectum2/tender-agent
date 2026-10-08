# APR-02 — fail-visible Data Platform authorization and index readiness

Date: 2026-10-08. Source evidence is the exact-number public RI223
32616445795 with 19 extracted RAR documents, 300 canonical chunk rows
in the isolated SQLite file, and the original existing Data Platform collection.

## Reproduced authentic failure

- A read-only analysis without the service's authorized internal API key
  got HTTP 401 from GET /v1/collections/.../stats, with an upstream
  invalid-internal-key diagnostic.
- The current analyzer incorrectly converted that authorization denial into
  status no_context with the misleading advice to prepare/reindex documents.
- Supplying the already-authorized production runtime key **in memory**
  (never printed or committed) completed the existing live Data Platform
  analysis: 10 original sections, 25 distinct cited original chunks and
  7 document evidence dossier categories with 3 cited excerpts each.
- Therefore the original collection was **not missing**. The analyzer was
  masking missing client authorization as an absent index.

## Bounded correction

- Preserve status no_context for HTTP 404 (collection not found) and for
  true missing/incomplete resources or embeddings.
- Return status failed and a source-neutral credential/configuration message
  on HTTP 401/403, without echoing upstream response bodies, secrets or URLs.
- Return status failed with fail-visible Data Platform service-unavailable
  diagnostics for other HTTP/provider/connection failures and malformed
  collection statistics, instead of fabricating absent documents.
- This changes the status of the existing read-only index readiness check,
  not the RAG engine, source extraction, DP transport, supplier fit,
  legal interpretation or autonomous GO/NO-GO.
- No EIS/ETP mutations, signing or payments; no secrets added to Git.

## Verification

- Real original RI223 without client key: failed, 0 analyzed sections,
  0 cited sources; explicit access-denied, readiness UNKNOWN.
- Existing authorized original analyzed read-only, as above, with no
  change to code path for a successful readiness check.
- HTTP 401, 403, 404, 503, connection refusal, invalid response, and
  incomplete 300/299 embeddings each have deterministic focused regressions.
- Full Tender Research: 519 passed, 1 skipped, 42 existing warnings.
- make check, focused Ruff and git diff --check: PASS.
- Exact-head CI and attributable Owner REVIEW before merge.
