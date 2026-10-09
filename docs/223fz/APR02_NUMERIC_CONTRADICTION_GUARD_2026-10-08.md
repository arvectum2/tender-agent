# APR-02: conservative numeric absence contradiction gate

Shared 223-FZ/44-FZ LocalChatLlmClient uses an existing fail-closed pathway. When the local LLM explicitly says a quantity, term, percentage or price is not specified, and an actually supplied original source text fragment contains a recognizable same-type explicit value, the new screen refuses the generated answer and falls back to retrieval-only source excerpts with a warning.

Original acceptance defect: 44-FZ procurement 0388100001826000047, winter diesel, model said volume not indicated even though supplied source stated 140 metric tonnes. The targeted guard detects this case. Six positive/negative unit cases and five prior evidence-gate cases passed. Full Tender Research: 532 passed, 1 skipped; make check passed.

Limits: conservative heuristic, no claim-level entailment proof; numeric values may refer to different lots, document revisions, qualifiers or rows. A matched value never proves legal effect or suitability. No application decision/GO/NO-GO. This mechanism can return false alarms, so it fails to the original cited retrieval context and human review rather than producing a definitive number. The earlier 20-case local model benchmark is a separate PR #244.
