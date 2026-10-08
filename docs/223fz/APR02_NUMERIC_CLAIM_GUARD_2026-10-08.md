# APR-02 — source-bound numerical claim safety gate

Shared Tender Research LocalChatLlmClient for 44-FZ and 223-FZ now checks one strict class of explicit numerical statements: a metric-tonnes value printed on the same answer line as a single literal chunk_id. When the cited, supplied source chunk itself contains exactly one metric-tonnes value, a mismatched model value fails closed to the existing retrieval-only original-source fallback and warning.

Measured failure exemplar: for authentic 44-FZ 0388100001826000047, source states 140 tonnes. A generated line claiming 150 tonnes and citing exactly that source is rejected. A claim of 140 tonnes referencing the same chunk is accepted by this identity/value screen (without proving unrelated assertions).

Ambiguity policy: unrelated units, absent source reference, reference on a different line, multiple source values (including multi-lot), and unrelated documents cannot be automatically resolved. The guard does not derive lot or effective source revision, does not infer law eligibility or GO/NO-GO and does not overwrite model answers with numbers. This narrow safety screen is deliberately incomplete and remains distinct from full claim entailment and future model comparisons.

Tests: source-unit contradictions, accepted matches, multi-number ambiguity, wrong reference, line boundary, different units and integration with the actual shared LLM completion validator. Full Tender Research: 542 passed, 1 skipped; make check passed.
