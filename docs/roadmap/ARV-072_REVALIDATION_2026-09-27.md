# ARV-072 revalidation — controlled competitive benchmark readiness

Date: 2026-09-27  
Task: `ARV-072-REVALIDATION-001`  
Authority: AUTO, repository-only validation

## Canonical question

The immutable ARV-072 snapshot requires a controlled comparison of Arvectum and at least five products on the same five real procurements. This slice checks whether the already-versioned protocol is ready for that live execution. It does not run competitors, modify benchmark truth, or authorize access.

## Evidence matrix

| Claim | Current repository evidence | Result |
|---|---|---|
| The benchmark protocol exists | `benchmarks/competitive/arv072/` contains the cohort, 100-point rubric, live-result schema, validator and gated report template; `docs/research/arv-072-competitive-benchmark.md` documents the same-input protocol. | Evidenced |
| Five distinct procurement cases are selected | `fixtures/competitive/arv072/cases.json` contains five unique 19-digit procurement numbers across five complexity roles. | Evidenced |
| Frozen accepted case inputs are ready | Every case has `live_ready: false`; all `source_bundle_sha256` and `truth_pack_sha256` values are null, with explicit blocking actions. | Not evidenced |
| Arvectum dependency gates are accepted for comparison | The package requires accepted ARV-003 output bound to frozen ARV-001 quality gates. Current canonical work remains the ARV-005 controlled pilot; no ARV-072 completion evidence closes those benchmark-specific gates. | Not evidenced |
| Authorized competitor access is available | Registry entries require authorized accounts, trials or demo invitations for comparable products. No repository evidence establishes those access grants. | Not evidenced |
| Live results exist | No redacted per-product/per-case result matrix or `ARV_072_COMPETITIVE_BENCHMARK_COMPLETE` marker is present. | Not evidenced |
| The merged domain regression registry completes ARV-072 | DOMAIN-REGRESSION-V1 records confirmed exposed cases and deterministic regression results while preserving blind/acceptance separation. It is useful infrastructure but is not five-product same-input live evidence. | Refuted |
| Public product claims may be scored | The protocol, rubric and README explicitly prohibit converting public claims into live-output scores. | Refuted |
| Existing package is internally consistent | Deterministic assertions from `benchmarks/competitive/arv072/validate.py` pass: required dimensions align with the schema, weights total 100, at least five external products exist, exactly five cases exist, and the draft report gate is present. | Passed |

## Validation result

`ARV-072 benchmark package: OK`

This confirms contract consistency only. It does not make any case live-ready and does not satisfy access, human-review or accepted-output prerequisites.

## Regression/benchmark boundary

`DOMAIN-REGRESSION-V1-001` is complete and valuable: it freezes confirmed failures as exposed regression cases with provenance and anti-circularity controls. ARV-072's remaining result is different: blind same-input outputs from comparable products, two runs per product/case, independent reviewers, adjudication, and retained evidence hashes. Exposed regressions cannot be silently reused as blind competitive proof.

## Residual gap

Before live execution, a separately admitted slice must establish all of the following without weakening the frozen method:

1. accepted source bundles and truth packs with immutable hashes for all five cases;
2. accepted Arvectum output/dependency gates for the identical inputs;
3. authorized, terms-compliant access to at least five comparable products;
4. frozen supplier context and question-set hashes;
5. two independent reviewers and an adjudication process;
6. evidence retention and redaction locations;
7. zero post-output edits to truth, comparator, normalizer or rubric.

## Bounded successor candidate

`ARV-072-CONTROLLED-LIVE-BENCHMARK-001` — `candidate_not_admitted`.

It may execute only the existing five-product/five-case protocol after every prerequisite above is evidenced under separately applicable authority. It must stop before unauthorized login or registration, vendor contact, purchase, terms acceptance, credentials, private/customer data, inferred scoring, post-output benchmark mutation, procurement action or any other external effect.

## Decision

ARV-072 is `revalidated_residual_gap`. Repository preparation is complete and internally consistent; live competitive execution remains unperformed and blocked by frozen-input, accepted-output, authorized-access and human-review prerequisites.
