# APR-02 — local Qwen generative 44-FZ / 223-FZ ten-domain evaluation

Status: 20/20 original-source local model generation requests completed; automated identity checks below. Semantic quality not exhaustively assessed.

## Method

- Mac mini local Qwen2.5-14B-Instruct Q4_K_M loaded via llama-server localhost:8088, temperature=0, max_tokens=300, context 8192.
- Original 223-FZ procurement 32616445795, 19 source documents, 300 document chunks in read-only original SQLite; 44-FZ procurement 0388100001826000047, 10 source docs, 233 source chunks in a separate original read-only SQLite.
- Ten same *topic groups* per regime: object, scope, timeline, application composition, qualification, evaluation, pricing, contract, security and restrictions; wording and source documents are regime-specific.
- This is a manually selected file-name/source-excerpt probe: up to two original chunks per section, **not** retrieval quality assessment or full-document legal reading. Missing evidence can mean missing selected excerpts.
- Each request includes exact persisted chunk IDs, source filename, bounded source excerpt, asks for citation per fact and UNKNOWN when not supported.
- Captured fields: model, elapsed seconds, token usage, finish_reason, full model text, cited UUIDs, unknown IDs and errors. Raw results and original evidence never committed to Git.
- Identity-verified citation does not prove semantic correctness. Compare source propositions/omissions by manual source review and do not infer company fit or GO/NO-GO.

## Results

Complete local source-ID audit (2026-10-08):

| Regime | Cases | Clean finish + valid cited UUIDs | No UUID citations | finish_reason=length | Unknown or mutated cited UUID | Request errors | Model time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 223-FZ | 10 | 2 | 6 | 3 | 0 | 0 | 122.06 s |
| 44-FZ | 10 | 5 | 3 | 2 | 0 | 0 | 122.44 s |

Uncited and truncated categories overlap; do not add their counts. A UUID-accepted response may still contain unsupported or omitted facts. These are **not accuracy rates** and do not establish which regime is harder; this is one tender per law, hand-selected source snippets, 300-token caps.

Manual spot check: 44-FZ object/scope selected source fragments contain **140 metric tonnes** (one fragment starts with the quantity, another contains it at char 1309, beyond the 1300-char cut). The generated 44-FZ scope response incorrectly stated that volume was not provided despite the first selected chunk stating 140 tonnes. This is a **second independently observed omission** following the smaller smoke benchmark.

The 223-FZ subject answer identifies media/information space monitoring, consistent with the original technical specification, but has no exact source UUID, hence does not pass the evidence integrity gate.

Local raw responses, original source references and checkpoint are stored in the authorized Mac mini runtime at /Users/master/arvectum-runtime/llm-benchmark-20261008/ten-section/results.json. Only this sanitized summary and generic summarizer tests are published.

Next steps: source-aware automatic entailment/reconciliation for numeric constraints (price, dates, volume), answer citations per claim; iterate prompt and model comparison with controlled input examples. Do not elevate local Qwen synthesis to GO/NO-GO or supplier qualification.
