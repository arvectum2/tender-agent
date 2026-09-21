# ARV-004 revalidation — 2026-09-22

## Historical scope

`docs/roadmap/master-roadmap.yaml` records ARV-004 as the historical Hermes adapter and pilot feedback loop, dependent on ARV-003 and originally targeting an adapter to the Hermes orchestrator plus collection of pilot feedback.

## Current repository evidence

Repository-wide default-branch code searches for `Hermes`, `HermesClient`, `Feedback`, and `llm` return no current implementation matches. The current recursive tree does retain the historical roadmap item but exposes no dedicated Hermes adapter or pilot-feedback implementation path. This is materially different from ARV-003, which has a completed revalidation checkpoint and is therefore skipped by deterministic continuation.

The bounded conclusion is therefore **not** that a new Hermes integration should be implemented. Current evidence only establishes that the historical ARV-004 implementation surface is absent from current main or has been superseded without a source-traceable replacement carrying the historical name/contract.

## Revalidation result

- ARV-003 dependency is satisfied by its completed revalidation checkpoint.
- No current repository-owned Hermes adapter implementation was found by deterministic code search.
- No current repository-owned pilot-feedback implementation was found by deterministic code search.
- No external model/provider call was made and no authenticated/private system was accessed.
- A successor implementation is intentionally **not admitted** because current canonical evidence does not define a safe provider/model contract, acceptance criteria, or authority for reconstructing the historical integration.

## Residual

`ARV-004-HERMES-FEEDBACK-CONTRACT-001` is recorded only as `candidate_not_admitted`: define, under separate admission, whether the historical Hermes/feedback capability is still desired and what repository-owned interface/acceptance criteria apply. This candidate must not infer provider architecture or make external calls.

## Gate

This revalidation may be prepared for review, but automatic merge is prohibited while Company AM-4 is REVIEW-due at 10/10. No production, procurement, legal, commercial, financial, deployment, external-communication, secrets, or customer-data effect is in scope.
