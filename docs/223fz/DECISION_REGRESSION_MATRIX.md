# 223-FZ Decision Core v1 — frozen pre-SUT regression matrix

Status: **FROZEN BEFORE SUT TUNING**. Task: `223FZ-DECISION-V1-001` / issue #70.

This packet freezes expected behavior before any 223-FZ decision-rule implementation. It deliberately does **not** invent legal/procedural semantics. The merged 223-FZ intake contract supplies source-bound procurement facts and explicit ambiguity/review reasons; the existing Decision Core supplies regime-neutral evidence and contradiction primitives. Until a separate source packet proves a regime-specific hard rule, 223-FZ candidates must fail closed rather than inherit 44-FZ-only assumptions.

| Case | Source-bound input | Frozen expectation | Why |
|---|---|---|---|
| `223-go-capable-candidate` | regime=`223fz`; title/deadline/price each have source refs; supplier profile present; no contradictions | `NEEDS_REVIEW`, no hard blocker | Facts may be KNOWN, but absence of independently frozen 223-FZ readiness semantics must not be promoted to GO. This is the GO-capable candidate required by #70, not an authorization to participate. |
| `223-hard-blocker-candidate` | regime=`223fz`; source-bound deadline status says expired | `NEEDS_REVIEW`, no `APPLICATION_DEADLINE_EXPIRED` hard blocker yet | The existing 44-FZ hard-blocker rule is not silently projected to 223-FZ without an independently frozen regime-specific source basis. |
| `223-missing-evidence` | regime=`223fz`; deadline/price values exist but source refs are missing | `NEEDS_REVIEW`; affected facts UNKNOWN | A value without source binding is not a Decision Core fact. |
| `223-contradictory` | regime=`223fz`; source-bound facts plus non-empty contradictions | `NEEDS_REVIEW`; `SOURCE_CONSISTENCY=REVIEW` | Contradiction handling is regime-neutral and fail-closed; no legal interpretation is needed. |
| `44-regression-control` | existing grounded 44-FZ Decision Core fixture | unchanged existing expectations | 44-FZ behavior is a regression control and must not be retuned to make 223-FZ pass. |

## Frozen invariants

1. Decision output and customer projection must expose normalized procurement regime.
2. `223fz` never falls through to 44-FZ-only hard blockers/readiness semantics.
3. Shared source-bound facts (`procurement_title`, `application_deadline`, `nmck`) may be KNOWN for either regime; KNOWN is not equivalent to GO.
4. Source contradictions always force manual review.
5. Unsupported 223-FZ contract/risk/deadline legal semantics are explicit UNKNOWN/NEEDS_REVIEW.
6. Human control and all existing `external_action_allowed=false` safety flags remain unchanged.
7. This file is regression truth for this increment. After SUT output is observed, expected outcomes above must not be edited to improve the result; any newly exposed case is regression-only unless an independent Owner-approved benchmark cycle is opened.

## Evidence boundary

The repository currently contains a merged, audited read-only 223-FZ intake path (`223FZ-INGEST-V1-001`, PR #80) and no independently frozen repository-owned legal/procedural source packet authorizing additional 223-FZ hard rules. Therefore this increment starts with conservative regime dispatch and explicit unknowns. Adding a 223-FZ hard blocker or positive GO rule requires a separate traceable source artifact and REVIEW before the rule can become normative.
