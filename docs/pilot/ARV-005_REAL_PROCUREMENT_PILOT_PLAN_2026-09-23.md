# ARV-005 — Real procurement pilot on Mac mini

Date: 2026-09-23
Status: admitted technical pilot execution
Canonical task: `ARV-005-CONTROLLED-PILOT-EVIDENCE-001`

## Owner direction

Use the existing Mac mini as the pilot server. Do not rent/migrate to VPS for this pilot. Move from repository-only validation to controlled runs on real public procurements.

## Safety boundary

Allowed: read-only public EIS/223-FZ discovery and document intake, local parsing, local embeddings, local LLM inference, deterministic Decision/Commercial Core, report generation, regression recording.

Not allowed: procurement submission/modification, EIS/ETP authenticated consequential actions, EDS/signing, supplier/customer outreach, payments/commitments, production-network/provider mutation unrelated to the Mac mini pilot, or claiming human/commercial acceptance that did not occur.

## Runtime baseline

Before counted runs, prepare a fresh canonical runtime from exact `arvectum2/tender-agent/main` without overwriting the existing legacy runtime copy.

Generation model for the pilot: the already-running local llama.cpp endpoint on loopback, currently exposing `arvectum-gemma4-12b-it-qat-q4_0`.

Retrieval embeddings: the already-running local Qwen3-Embedding-4B endpoint on loopback.

The existing Ollama endpoint is not the primary pilot generation path. RAG answer-generation remains disabled during the first wave so controlled LLM extraction can be measured separately.

Required local controlled-provider settings:
- `AI_CORP_LLM_PROVIDER=openai_compatible`
- `AI_CORP_LLM_MODEL=arvectum-gemma4-12b-it-qat-q4_0`
- `AI_CORP_OPENAI_BASE_URL=http://127.0.0.1:8081/v1`
- local dummy bearer credential only, never committed
- `AI_CORP_LLM_STORE_RAW_RESPONSE=false`
- `AI_CORP_LLM_ALLOW_RAW_PARTNER_DATA=false`

## Pilot design

### Wave 0 — infrastructure and model smoke (not counted)

1. Pin a fresh Mac mini runtime to exact canonical main.
2. Run repository checks and Mac mini health/preflight.
3. Verify public EIS transport read-only.
4. Verify local embeddings.
5. Verify controlled local-LLM schema path end-to-end on non-sensitive fixture data.
6. Freeze the exact runtime commit and model aliases used for counted runs.

### Wave 1 — three real 44-FZ procurements

Select three public goods procurements in/near electrical equipment:
- one simple single-lot/catalog-like case;
- one multi-position/specification-heavy case;
- one contract/risk-heavy case.

Run the full read-only path: discovery -> documents -> completeness -> deterministic extraction -> Decision Core -> controlled local LLM -> report. Do not change model/config between the three cases.

### Wave 2 — five further real 44-FZ procurements

Choose five additional public cases before inspecting model outputs. Include different customers/document structures and at least two cases expected to end in NEEDS_REVIEW or material blocker.

Only regressions found in Wave 1 may be fixed before Wave 2. Freeze the five registry numbers before those fixes are evaluated.

### Wave 3 — four confirmation 44-FZ procurements

Four previously unseen public cases. No tuning on these cases before completion. This is the core confirmation set.

Core pilot denominator: 12 real 44-FZ procurements.

### Exploratory 223-FZ wave — three procurements

Run three public 223-FZ cases after the 44-FZ core. Score separately because current 223-FZ breadth is intentionally incomplete. Use failures to identify concrete lots/positions/change/protocol/lifecycle gaps; do not invent legal semantics.

Total planned real runs: 15 (12 core 44-FZ + 3 exploratory 223-FZ).

## Per-run evidence

Record:
- registry number/law/source and exact runtime commit;
- document count and completeness result;
- deterministic analysis status;
- local LLM invoked/provider/model/schema-validation result;
- LLM latency and failure/fallback reason;
- source-grounded claims and unsupported/rejected claims;
- Decision Core output and blockers;
- report generation status;
- operator corrections required;
- technical defects/regressions found;
- no external consequential action declaration.

Do not commit raw private/customer data. Public procurement identifiers and sanitized technical evidence may be committed.

## Gates

Wave 1 -> Wave 2:
- all three runs complete without silent fallback;
- every local-LLM section reports explicit invoked/fallback provenance;
- no unsupported accepted factual claim is observed in the technical review;
- any critical ingestion/source-binding defect is fixed or fail-closed before continuing.

Wave 2 -> Wave 3:
- no unresolved critical source-attribution or cross-procurement contamination defect;
- schema/fail-closed behavior is stable;
- regressions found so far are captured.

Technical pilot completion:
- 12 core 44-FZ real runs completed;
- three 223-FZ exploratory runs completed or explicitly blocked with source-bound reasons;
- aggregate technical report produced;
- every confirmed product defect has a regression issue/case or explicit bounded follow-up;
- human usefulness/commercial acceptance is reported separately and never inferred by the executor.

## Stop conditions

Stop counted runs and fail closed if:
- source ownership/cross-case isolation is violated;
- accepted facts cannot be traced to procurement-owned evidence;
- local LLM silently falls back while provenance says it ran;
- public-source acquisition begins requiring authenticated/consequential ETP actions;
- model/runtime configuration changes without a new frozen wave boundary.
