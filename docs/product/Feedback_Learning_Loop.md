# Feedback & Learning Loop — post-MVP successor to Hermes foundation

## Status

- Canonical roadmap item: `ARV-004`.
- Product phase: **post-MVP**.
- Execution admission: **not admitted**.
- BASE dependency: none. `BASE-011` is treated as the completed Hermes infrastructure foundation.
- Human-control boundary: unchanged. GO / NO GO / DEFER remains an attributable human decision.

## Why this is separate from BASE-011

The historical BASE-011 foundation is already present: Hermes client/fallback behavior, runtime context assembly, category profiles, normalization, quality gates, procurement feedback/memory primitives, eval-case generation, supplier-readiness helpers and bid-decision helpers all exist with focused tests.

The unfinished value proposition is different: learning safely from real user corrections across production use. That is a post-MVP product capability, not a prerequisite for operating Tender Agent today.

## Goal

Turn reviewed human corrections into durable, auditable quality improvements without creating a second autonomous decision engine.

Target loop:

```text
user correction
→ attributable immutable review
→ accepted correction
→ regression case
→ validation against current corpus
→ reusable rule candidate
→ reviewed promotion
```

No correction becomes a global rule merely because it was submitted.

## Reuse-first implementation

Build on existing components rather than introducing a parallel subsystem:

- `TenderAnalysisFeedback` for captured corrections;
- `AgentMemory` for bounded feedback/rule memory;
- `TenderEvalCase` and the domain-regression corpus for reproducibility;
- canonical Customer / Project / Case ownership and tenant boundaries;
- Decision Core for source-bound decision semantics;
- existing evidence/provenance contracts for traceability.

External Hermes runtime is not required for this loop.

## First bounded stage

When ARV-004 is explicitly admitted after MVP usage produces meaningful real corrections:

1. expose correction/confirmation actions in the existing review UX;
2. bind each correction to user/reviewer, customer/project/case, analysis version and source evidence;
3. store the reviewed correction immutably with audit history;
4. generate or update a regression case from an accepted correction;
5. run the affected regression set before any reusable-rule promotion;
6. surface reusable-rule candidates for human review rather than applying them automatically.

## Promotion rules

A reusable rule must be evidence-backed, regression-tested and explicitly reviewed before it can influence unrelated procurements. Tender-specific factual memory remains tender-scoped. Customer-specific knowledge remains customer-scoped. Cross-customer promotion must fail closed unless a future reviewed policy explicitly permits it.

## Non-goals

This post-MVP loop does **not** introduce:

- autonomous company-agent execution;
- mandatory external Hermes server deployment;
- automatic self-modifying prompts or extraction rules;
- autonomous GO / NO GO / DEFER decisions;
- automatic ETP actions, signatures or submissions;
- cloud dispatch of confidential tender/customer data;
- a second decision engine parallel to the canonical Tender Agent Decision Core.

## Activation gate

ARV-004 stays outside the execution queue until both conditions are true:

1. production usage has produced a meaningful corpus of real, attributable corrections;
2. the Owner explicitly admits a bounded implementation slice.

Until then, the existing Hermes foundation remains available as tested internal infrastructure, while Tender Agent continues to use the canonical Data Platform → analysis → Decision Core → human decision flow.
