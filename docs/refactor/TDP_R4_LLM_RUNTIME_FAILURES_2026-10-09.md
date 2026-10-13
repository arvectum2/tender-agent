# R4 controlled LLM runtime: observable failures

The private Operator Workspace may be configured with a stub LLM provider. Data Platform health and a successful llama.cpp JSON smoke on port 8081 do not mean Tender Agent invoked the model.

The old _try_run_llm_workflow returned None for all exceptions without persisting the cause. The change now emits a safe controlled_llm_runtime_failed event with only exception type and provider mode. It never copies exception messages, secret keys, prompts, or procurement texts into the event. The existing fallback and human approval stay intact.

Mac mini full pytest on R3 branch: 3346 passed, 238 skipped, one R9 PostgreSQL backup restore matrix failed with pg_restore exit code 1; reproduced on prior branch. GitHub PR262 CI including PostgreSQL passed. This is not proof of fixing the local database environment.

Next: independently exercise configured model provider on private isolated test container, pin model and timeouts, audit schema validation and matched source facts; do not change live preview or public infrastructure.

## R4 follow-on: bounded, distributed excerpts from long source documents

An isolated real-EIS run for 44-FZ registry 0372200172326000015 was completed on 2026-10-09 against local Gemma 4 12B: 4/4 output sections PASSED (requirements, supplier questions, RFQ draft, contract risk memo), runtime 286 seconds; 7 technical requirements, 10 supplier questions and 5 contract risks returned. This run intentionally sent only the beginnings of real normalized document texts (6500/7500/7000 characters), **not full-source recall**. These numbers indicate schema compliance and nonempty artifacts, NOT factual quality or legal acceptance.

The next separate bounded module document_context_selection.py consumes the Data Platform-extracted normalized text and distributes attention across its beginning, scored procurement-relevant middle windows and the last window. It emits exact character range markers normalized:role:start-end and expressly marks each excerpt as unverified. Short documents are untouched. These markers do not claim a particular original XML field, PDF page or filename; those still require provenance through the strict original-file evidence pipeline. In the controlled workflow, long source data no longer silently overwhelms the prompt with hundreds of thousands of characters. Add a cross-file/file-id annotated retrieval corpus after reliable Data Platform chunk IDs and original locators are available.

This is not a proof of exhaustive document analysis: actual coverage/recall (Russian DOC/DOCX/PDF, annexes, obligations, prices), offset-to-original mapping, false findings, citations and quality gates remain R5 pending. Never promote generated risks/quotes to KNOWN without source evidence.
