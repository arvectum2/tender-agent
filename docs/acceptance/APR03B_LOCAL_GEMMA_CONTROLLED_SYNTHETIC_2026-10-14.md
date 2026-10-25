# APR-03B: actual local Gemma 4 controlled operator workflow, synthetic-only

Observed 2026-10-14 on Mac mini, isolated runtime QA. **TECHNICAL_LOCAL_LLM_PASS / HUMAN_SEMANTIC_AND_CURRENT_NOTICE_GATES OPEN.**

## Runtime

- Existing localhost-only llama.cpp server: `127.0.0.1:8081` (`llama-server 0.6.0`), model alias `arvectum-gemma4-12b-it-qat-q4_0` (locally installed GGUF). No model download, no service restart, no cloud provider used.
- Read-only `/health` and `/v1/models` returned expected values. Initial constrained `json_object` OpenAI-compatible synthetic request returned expected Boolean JSON.
- **Actual Tender Agent** `_OpenAICompatibleJSONProvider.generate()` using localhost synthetic fixture and schema returned `{"verified": false, "can_bid": false}`. This is actual project adapter transport and JSON decoding, not a fake provider.
- **Actual controlled 4-section operator workflow** called `run_controlled_operator_llm()` from the checked-out Tender Agent source with `AI_CORP_LLM_PROVIDER=openai_compatible`, `AI_CORP_OPENAI_BASE_URL=http://127.0.0.1:8081/v1`, `AI_CORP_LLM_MODEL=arvectum-gemma4-12b-it-qat-q4_0`, synthetic-only notice/spec/contract, no quote inputs and `provider_mode=llm`.
- Temporary isolated SQLite database `/tmp/ta-apr03b-synthetic-local-llm-20261014.sqlite` only; temporary env vars applied to one shell child process. Existing private preview ports 18083 and 18087, saved genuine EIS runs, source files and production untouched.

## Exact result

- Returned `resolved_provider=openai_compatible`, `analysis_mode=llm_tender_operator_provider`.
- Returned four section objects: `requirements`, `supplier_questions`, `rfq_draft`, `contract_risk_memo`.
- **4** persisted `runtime_control_traces` in temporary SQLite independently queried after execution: **4/4 `validation_status=PASSED`**, **4/4 `human_review_status=needs_human_review`**.
- Response contains `bid_decision=None` (no automatic bid decision); no bid-submission path was exercised.
- Total elapsed **69.4 seconds** on the existing local Mac mini server. No real buyer, registry number, commercial contract, protected partner content or external procurement endpoint was sent to the LLM.
- This **is not** an evaluation of model hallucinations, source-citation quality, real procurement feasibility or legal authority. The synthetic task is deliberately trivial; real official revision and human evidence-based review must be performed separately.

## Next Owner acceptance gate

Authorize/pin current official ЕИС original notice/revision and complete a protected workspace run with real analyzed documents (no archived export bypass); inspect claim-level verified citations, economic viability, supplier profile and model quality; human decides GO/NO GO/DEFER. Do not activate paid SaaS, ETP, signatures, contact buyers, production or the disabled watchdog.
