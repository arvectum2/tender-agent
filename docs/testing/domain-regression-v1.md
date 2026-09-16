# Procurement domain regression registry v1

`regressions/procurement/v1/manifest.yaml` is the repository-owned registry for **confirmed, exposed procurement regressions only**. It is not a new benchmark and it is not a place to invent speculative test cases.

## Lifecycle and anti-circularity

A case may enter the registry only after a concrete failure/edge case is confirmed in repository evidence. A former blind case may be registered only after its first immutable result is recorded; its manifest entry must retain a freeze reference and attest that truth was frozen before SUT and exposure happened after that first result. The registry never rewrites blind labels, benchmark truth, comparators, normalizers, or acceptance artifacts.

The three classes remain separate:

- **blind benchmark** — truth is frozen before SUT and stays in benchmark-owned artifacts;
- **acceptance** — a release/task gate with its own evidence and authority;
- **exposed regression** — a previously observed failure that may be rerun freely to prevent recurrence.

Every registry case is therefore `benchmark_class: regression_only` and `exposure_status: exposed_regression`. Adding a blind or acceptance case directly to this registry is invalid.

## Required evidence

Each case records regime, component, failure class, origin issue, source provenance, immutable evidence SHA-256, expected invariant and one or more repository pytest node IDs. Public-source identifiers/URLs are retained where available. Private/customer material must not be copied into the repository unless an independent approved sanitization/data boundary already exists.

The initial v1 seed contains only confirmed repository-owned 44-FZ failure families: the exposed customer-identity boundary failure from case 11 and the active-notice-revision attachment-mixing failure from case 14. 223-FZ/private cases are added only after those paths have confirmed real regressions.

## Commands and deterministic report

Validate the registry:

```bash
python scripts/domain_regression.py validate --json
```

Run all registered cases and produce the CI report:

```bash
make test-domain-regressions
```

The report is written to `output/domain-regression-v1.json`. It deliberately omits timestamps and test durations; for an unchanged manifest and unchanged pass/fail outcomes, its contents are stable. Cases can also be filtered with `--case-id` or `--component` for Decision Core, Commercial Core, ingestion or other registered subsets.

A failing registered test fails the command. Manifest/schema, duplicate-ID, provenance, evidence-hash, repository-path and former-blind anti-circularity violations fail before tests run.
