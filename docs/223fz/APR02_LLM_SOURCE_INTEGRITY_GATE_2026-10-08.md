# APR-02: shared LLM source integrity gate

Based on authentic Qwen2.5-14B Q4 Mac mini smoke: RI223 32616445795 and 44-FZ 0388100001826000047.

- Shared LocalChatLlmClient for 223-FZ and 44-FZ rejects a generated answer with no exact chunk citation, altered or unknown chunk ID, or explicit truncated/filtered finish reason.
- Existing analysis-service fallback returns retrieval-only source excerpts and warning, not unsupported generated text.
- The validator confirms cited ID identity ONLY: it does not establish claim entailment, document applicability or GO/NO-GO.
- Original benchmark observed one fabricated RI223 UUID and uncited 44-FZ answer that missed source quantity 140 tonnes. These facts remain genuine measured defects, not fixed model quality.
- Five adversarial tests added; full Tender Research 526 passed, one skipped; make check passed.
- Full multi-section generative evaluation remains a separate task.
