# R4 controlled LLM runtime: observable failures

The private Operator Workspace may be configured with a stub LLM provider. Data Platform health and a successful llama.cpp JSON smoke on port 8081 do not mean Tender Agent invoked the model.

The old _try_run_llm_workflow returned None for all exceptions without persisting the cause. The change now emits a safe controlled_llm_runtime_failed event with only exception type and provider mode. It never copies exception messages, secret keys, prompts, or procurement texts into the event. The existing fallback and human approval stay intact.

Mac mini full pytest on R3 branch: 3346 passed, 238 skipped, one R9 PostgreSQL backup restore matrix failed with pg_restore exit code 1; reproduced on prior branch. GitHub PR262 CI including PostgreSQL passed. This is not proof of fixing the local database environment.

Next: independently exercise configured model provider on private isolated test container, pin model and timeouts, audit schema validation and matched source facts; do not change live preview or public infrastructure.
