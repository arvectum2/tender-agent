# PILOT-001 — Operational multi-case validation

Status: `BLOCKED_P0_CLOSURE_REQUIRES_REVALIDATION`

## Purpose
Validate the accepted Mac mini autonomous procurement path across several independent real procurements before calling the read-only Tender Agent workflow operationally ready.

## Mandatory preflight
The first attempted execution on 2026-09-01 did not constitute a valid multi-case pilot: runtime HEAD `84f859ca4998b58fd689dabc2221c88fef3a9420` is an ancestor of canonical `main`, and `scripts/run_macmini_autonomous_procurement.py` was added later.

The runtime was reconciled to canonical `main`, its environment was restored from the locked dependencies, and the runner was hardened to preserve terminal-attempt evidence.

This resolves `RUNTIME_PRECONDITION_STALE_CHECKOUT`; it does not itself prove analysis quality or replace PO review.

## Current execution result

The local ignored evidence set contains a seven-attempt diagnostic series that reached five unique reports, but it is not countable for pilot completion:

- Five unique 44-FZ procurements reached `MACMINI_AUTONOMOUS_PROCUREMENT_E2E_REPORT_READY` with downloaded documents and saved HTML reports.
- Two selected procurements stopped fail-closed at `documents_required`; no analysis or report was fabricated.
- Every terminal attempt has `runner.json` and `_evidence.md`; ready attempts also retain their HTML report.
- All five ready attempts used `fallback_deterministic_adapter`; no local LLM completion was recorded. Each recommendation remained `manual_review_required`.
- A subsequent source-grounding audit found unsupported generic fallback claims in two ready reports. The series is invalidated pending a clean revalidation after the D04 runtime integration.

The D04 integration was added to runtime and one targeted read-only remediation run showed the forbidden templates absent, replaced by explicit `INSUFFICIENT_EVIDENCE` statements. A new five-unique-case series on the corrected SHA is still required before PO review.

## Provisional defect register

| ID | Cases | Severity | Layer | Classification | Evidence | Next action |
|---|---:|---|---|---|---|---|
| `PILOT-001-D04` | 2 ready attempts observed; all fallback reports affected by missing runtime integration | P0 | fallback runtime integration | `SYSTEMATIC` | Case review found unsupported generic claims such as a 15-day delivery condition and delivery/unloading assumptions. The actual runtime omitted the already-prepared source-grounding layer. | D04/D04.2/D04.3 integrated; targeted remediation run passed. Execute a fresh five-unique-case revalidation, then have PO assess source support and usefulness. |
| `PILOT-001-D05` | 2 of 7 attempts | P2 | public document intake | `PROCUREMENT_SPECIFIC` | The selected public procurements were stopped at `documents_required` and no report was produced. | Retain as correct fail-closed behavior unless PO finds the document-set classification wrong. |

The P0 closure is not complete until the fresh multi-case revalidation and PO review are recorded.

## Safety boundary
Read-only only: no bid submission, ETP mutation/login, supplier/customer messages, EDS, captcha bypass, source fabrication, ARV-001 evidence mutation, or product hot-fixes between cases.

## Runner
```bash
python3 scripts/run_macmini_autonomous_procurement.py \
  --query "<query>" \
  --law 44fz \
  --min-relevance 20
```

Success: `MACMINI_AUTONOMOUS_PROCUREMENT_E2E_REPORT_READY`  
Safe block: `MACMINI_AUTONOMOUS_PROCUREMENT_E2E_BLOCKED`

## Case set
Exercise at least five UNIQUE real 44-FZ procurements. Initial queries:
1. `электротехническое оборудование`
2. `автоматические выключатели`
3. `кабель силовой`
4. `контакторы`
5. `светильники светодиодные`

Reserve queries: `шкаф электрический`, `реле электрическое`, `источник бесперебойного питания`, `розетки выключатели`, `электромонтажные материалы`.

Every counted case must have a unique registry/EIS number. Do not change relevance logic or thresholds to force results.

## Evidence
Keep live artifacts local under ignored `company_agent_runs/PILOT-001-<UTC timestamp>/`. For each attempt preserve runner output, HTML report if produced, and `_evidence.md` containing query, registry, source URL, run ID, result, recommendation, document status/count, analysis mode, local-LLM/fallback evidence, report status/path, duration, intervention, PO verdict/corrections, and defect IDs. Until actual human review, PO verdict is `PENDING_REVIEW`.

## Defects
Record stable ID, affected cases, frequency, severity P0-P3, layer, classification (`SYSTEMATIC`, `PROCUREMENT_SPECIFIC`, `UNRESOLVED`), evidence, and next action. Unsafe external side effect, corrupted evidence identity, fabricated source fact, silent LLM/fallback misreporting, or material unsupported human-facing conclusion is P0.

## Completion
PILOT-001 is complete only after 5+ unique real procurements are exercised on one unchanged reconciled runtime SHA, every attempt has evidence, reports have PO verdicts, and defects are consolidated/classified.

Final decision must be exactly one of:
- `OPERATIONALLY_READY_FOR_RESTRICTED_READ_ONLY_PILOT`
- `NOT_READY_SINGLE_P0_CLOSURE_BRANCH_REQUIRED`

Neither outcome authorizes autonomous bid submission, ETP mutation, supplier messaging, EDS use, or a mass external pilot.
