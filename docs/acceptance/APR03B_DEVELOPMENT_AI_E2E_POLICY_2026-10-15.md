# APR-03B: Owner-delegated AI expert E2E acceptance (15 Oct 2026)

## Accepted owner decision

For this DEVELOPMENT E2E stage, ChatGPT's source-grounded procurement reviews count as expert acceptance judgements. A separately hired human expert and 20 individually signed human legal gold reviews are NOT required to finish this stage. The Owner will contribute corrections only AFTER a stable end-to-end workflow.

Reviewer identity is recorded as owner_delegated_chatgpt, not a qualified independent human or legal signatory. Development acceptance does not authorize an actual tender participation decision.

## Verifiable E2E criteria

1. A real numbered EIS notice with retained verifiable original official files and SHA256 receipts.
2. Unified user flow: source search/import, originals, extraction, full local LLM analysis, report with source citations, persisted history/reopen and read-only registry.
3. At least one independently confirmed cited material fact, zero unsupported material assertions disguised as facts; UNKNOWN remains explicit.
4. Historical notice without current revision verification: official PDF/DOCX export must be rejected with HTTP 409. Current-revision exports require separate evidence.
5. Never submit bids, sign, contact suppliers, mutate ETP/production, make payments or assert automatic legal GO.
6. Technical E2E must actually work; an AI opinion does not excuse a broken interface, missing documents or deterministic fallback when a model run is claimed.

The acceptance checklist is implemented in scripts/acceptance/apr03b_development_e2e_gate.py. Its JSON receipt is a checklist, NOT cryptographic proof on its own. Every evidence_ref must be backed by actual independent runtime/source records outside the public repository. Tests include deliberate failure on a missing step, unsupported claims, fallback instead of local LLM, archival export error and unsafe external actions.

## What is already evidenced, and what is not

- Historical private Mac mini run toa-run-20261012200402-7249ed: six authentic Museum of Bread EIS files, completed extraction and persisted workspace history, with a deterministic fallback report. The earlier report had gaps in claim-level citations; that report is NOT a full-LLM E2E acceptance.
- Later isolated current-main preview returned health 200 and correctly denied archived official PDF/DOCX with HTTP 409.
- Independent source-level AI reviews for three development cases on the separate draft R4 branch demonstrate useful source-grounded judgments but do not prove those judgments were automatically produced in the current product UI.
- Blind benchmark source cohort and externally signed human gold are separate later calibration artifacts, not a prerequisite for APR-03B E2E. Do not alter held-out truth or assert independent precision/recall from AI self-evaluation.

**Stage result at policy adoption:** OWNER_AI_EXPERT_RULE_ACCEPTED; ACTUAL_CURRENT_FULL_LLM_E2E_NOT_YET_VERIFIED. Proceed with engineering validation and functional fixes immediately, without waiting for new human legal reviews. Only mark APR-03B DONE once the verifiable full user flow passes.

## After acceptance

Continue APR-04 company onboarding, APR-05 staging SaaS and APR-06/07 commercial and quality measurement. Owner expert corrections become a later reviewed feedback dataset. Existing legal, bid, financial, signature and deployment restrictions stay unchanged.
