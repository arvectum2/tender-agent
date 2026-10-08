# APR-02: positive numeric claim source integrity screen

A conservative check on top of PR #245 numeric-absence guard, shared by 223-FZ and 44-FZ local LLM RAG client. If a generated answer asserts an explicit number+unit not observed in any of the original supplied source chunks, generated output is refused in favor of the existing retrieval-only original-source fallback and human review.

Examples: original 44-FZ source 140 tonnes vs generated 150 tonnes, or 223-FZ criteria 40/60% vs generated 45%; costs compared in rubles only. Negative controls: matching quantity and percentages, date without supported unit, correct price value.

This checks evidence string presence only. It does NOT prove the answer is supported by the exact cited chunk, nor that a numeric value belongs to the same lot, active revision, clause or applicable procurement regime; no conversion/currency inference and no GO/NO-GO. May reject calculated values not literally appearing in the source.

Original EIS document bytes stay outside Git. Six new positive/negative tests, full Tender Research 539 passed 1 skipped, make check PASS. This is a dependent branch: predecessor PR #245 must pass exact-head CI and merge before this branch is independently reviewed and merged.
