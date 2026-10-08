# APR-02: genuine local Qwen2.5 14B smoke benchmark (223-FZ versus 44-FZ)

Date: 2026-10-08. This is an initial two-case smoke benchmark, not full
supplier qualification, legal review or controlled statistical comparison.
Original documents and complete model responses remain outside Git.

## Local runtime

- Ollama at localhost:11434 has no registered models, but local SSD has
  Qwen2.5-14B-Instruct-Q4_K_M.gguf (~8.4 GiB).
- Reused native llama-server on localhost:8088, context 8192, confirmed
  /health ok. Model: Qwen2.5-14B-Instruct Q4_K_M; temperature 0,
  max_tokens 250; OpenAI-compatible local API.
- Earlier real Data Platform retrieval acceptance was use_llm=False;
  10 sections, 25 citations and seven dossier categories did NOT
  exercise Qwen2.5 generative answers.
- These two requests used *original SQLite chunks with exact chunk IDs*.
  GPT-6 engineered and assessed outputs but did not serve either request.

## Authentic 223-FZ case 32616445795

- Original RI223 RAR corpus: 19 documents, 300 canonical source chunks.
  Four original excerpts: two technical-specification DOCX, two evaluation
  methodology DOC.
- Local Qwen 19.95 seconds, 206 completion tokens. Correctly recognized
  media-monitoring services, 2027 performance and 40% price versus 60%
  non-price criteria (source-observed facts, not complete review).
- CRITICAL source-citation mismatch: model cites
  ce05b458-5062-4b62-bbc3-dce35b66b665; original supplied source ID is
  ce05b458-5069-4b62-bbc3-dce35b66b665. Another cited UUID matched.
  Citation integrity FAILED even though some facts were accurate.

## Authentic 44-FZ case 0388100001826000047

- EIS recovery corpus: 10 document records, 233 text chunks; four original
  excerpts: two object-description XLSX and two application-requirements DOC.
- Local Qwen 19.34 seconds, 250 completion tokens (cap reached, answer
  truncated mid-sentence).
- Correctly identified winter diesel fuel for Chukotka UGMS, but wrongly
  said quantity and units were not specified. An original supplied chunk
  explicitly states 140 metric tonnes.
- The answer contained zero valid source chunk UUID citations. Source
  grounding FAILED. No complete application requirements conclusion.

## Limits and next steps

- Different cases/questions: cannot infer that one procurement regime is
  intrinsically easier, or report model accuracy from two prompts.
- Deterministic audit script in scripts/benchmarks/local_llm_citation_audit.py
  checks returned UUIDs only against supplied chunk IDs and marks uncited
  answers; it is NOT legal/semantic evaluation.
- Next gate: validate every cited chunk ID against actual source; require
  per-claim citations, cap/truncation checks and reject or retry mutated
  citations; benchmark all 10 sections with same controlled scoring rubric,
  then evaluate actual company fit only with authorized profile evidence.
- No unsupported legal status, supplier eligibility, risk grade, GO/NO-GO,
  EIS/ETP write, signing or payment.
- Full original generated answers and model metadata are stored in
  /Users/master/arvectum-runtime/llm-benchmark-20261008/results.json.
