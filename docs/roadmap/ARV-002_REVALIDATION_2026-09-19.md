# ARV-002 revalidation — 2026-09-19

Task: `ARV-002-REVALIDATION-001`
Base: `128c6328b6a6b7ed40cc60e94e4712dbbc0d9f2b`

## Canonical source

The immutable ARV-002 snapshot says:

- stable live end-to-end pipeline without hidden fallback;
- R7 already proved live exact-number flow, production source graph, persistent artifacts, recovery and controlled-pilot deployment;
- the next result is to keep the live E2E path as a release/integration regression baseline.

This revalidation does not rewrite that snapshot. It checks the current repository and public read-only source behavior.

## Deterministic repository evidence

Focused current-main checks:

```text
63 passed
```

Coverage set:

- `tests/test_tender_operator_agent_procurement_discovery.py`
- `tests/test_tender_operator_agent_search_to_getdocs_flow.py`
- `tests/test_procurement_source_graph_production.py`
- `tests/test_procurement_source_graph_json_roundtrip.py`
- `tests/test_runtime_preflight_no_fallback.py`
- `tests/test_public_eis_transport_policy.py`
- `tests/test_pilot_backup_restore_scripts.py`

The set verifies the current exact-number search branch, search-to-document handoff contract, production source graph, JSON round-trip stability, fail-closed runtime preflight, direct EIS transport policy and pilot backup/restore scripts.

Additional persistence/recovery checks:

```text
32 passed, 12 skipped
```

Coverage set:

- `tests/test_tender_operator_agent_report_export.py`
- `tests/test_recovery_r4_integration.py`
- `tests/test_recovery_r5_integration.py`
- `tests/test_pilot_backup_restore_scripts.py`

The skipped cases are environment/profile-gated tests; no failure was observed in this focused run.

The repository default CI also executes `make test`, so these deterministic regressions are part of the ordinary release-quality job.

## Read-only live EIS evidence

A public, unauthenticated, read-only exact-number lookup was executed through the current production parser for registry number `0888500000226000399`.

Observed search response:

- `status=parsed`
- `outcome=success_with_results`
- `returned_count=1`
- `eis_pages_fetched=1`
- source `public_eis_html_44fz`
- exact-number branch did not attach supplier relevance state.

The public common-info page for the same notice was then read through the current detail-context extractor. It returned a clean explicit customer role:

```text
ДЕПАРТАМЕНТ ЗДРАВООХРАНЕНИЯ ЧУКОТСКОГО АВТОНОМНОГО ОКРУГА
```

and coherent title/date/deadline/price metadata.

No authentication, submission, communication, payment, signing or other consequential action was performed.

## Proven residual gap

The same live search-result card exposed a malformed `customer_name`: the value was polluted by page JavaScript rather than a customer organization.

The current parser has a broad search-card fallback in `src/tender_research/providers/public_44fz_search.py`:

```python
re.search(r'Заказчик[^:]*:\\s*([^<]+)', entry_html, re.IGNORECASE)
```

On the current EIS layout that fallback can cross into script text. The later common-info/detail extractor is stricter and produced the correct customer, so the handoff path can self-correct when the detail page is available; the discovery card itself is nevertheless not clean enough to mark ARV-002 fully confirmed.

## Bounded successor candidate

Candidate only; **not admitted for implementation by this revalidation**:

`ARV-002-LIVE-CUSTOMER-PARSE-001 — Exact-number live customer parsing regression gate`

Bounded scope:

1. constrain search-card `customer_name` extraction to explicit visible customer-scoped evidence;
2. if such evidence is absent/ambiguous, return `null` rather than organization-like script or placement text;
3. add a deterministic fixture reproducing the observed current EIS layout and protect it in the default test suite;
4. preserve common-info/detail-page customer precedence and the existing exact-number/no-hidden-demo-fallback behavior;
5. no external-effect, production, procurement, benchmark-truth or authority change.

This candidate is directly traceable to ARV-002's stable-live-E2E/no-hidden-fallback objective and its release-regression-baseline next result.
