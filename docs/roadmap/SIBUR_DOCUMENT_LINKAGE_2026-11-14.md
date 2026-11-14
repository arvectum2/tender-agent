# Source-separated document persistence — 2026-11-14

Owner-authorized working DB ingestion continued from the existing 313 SIBUR tender rows. 90/90 supported URL captures completed, SHA verified: 42 DOCX, 33 XLSX, 15 PDF. 81 procedures linked. 116 distinct (tender_id, SHA256) links written into existing procurement_tender_documents, all matched to original source observations; repeat insert returned zero. No other source links present.

The full Data Platform prewrite backup was verified (SHA256 3eb6fbcc0f116e647fc483f2508f8beaf5c496a44021c58eb95b75f487346d80), as was the TA backup before linking (SHA256 6848339e80419ffcd07a6a8add1168bd5281c6c35adb3d7dd3e91c3e9195ac60). Internal runtime gate passed.

Dedicated collection tender-agent:sibur-public-research, owner tender-agent, allowed_consumers [tender-agent], llama_cpp/Qwen3-Embedding-4B dimension 2560. One exact original indexed through the existing authenticated DP SDK; independent collection stats confirmed one document, resource, chunk and embedding. Source SHA and DP resource/document identifiers retained in the TA link metadata. Existing internal API credentials used without changing credentials. Consumer-authenticated search and broader tenant integration still require verification; no result quality claim yet.

Original file serving remains an independent step: TA local download/extraction states stay pending, verified external capture and index status are explicit in raw_meta. The linker is insert-only except one-way attachment of verified DP index evidence; never overwrites divergent original observations. Production app path integration and testing incremental revision handling remain open. 426 of 516 referenced URLs remain uncaptured; some formats require separate adapters.

Next: resume bounded capture/processing and DP indexing, verify retrieval with authorized consumer identity, integrate TA file serving and relevance classification; continue GEH/ZMO discovery. No actual procurement submissions or commitments.

## Full observed attachment capture and initial text triage

All 516 allowlisted source URLs captured and SHA replay verified (513 unique original hashes, 229 procedures, 713 tender/document links). One source .ppt structurally verified as OOXML presentation; original bytes unchanged. Archive and legacy format bytes remain capture-only. 337 processing results: 329 extracted, 8 empty, 10 possible text caps; DOCX/XLSX pass complete, PDF/PPTX pilot performed. DP permanent collection contains 106 originals, 261 chunks and embeddings; 118 TA links carry index evidence. Lexical triage found 79 procedure candidates including 51 absent from metadata triage; not semantic or award acceptance. Reasoning API timed out at 30 seconds. Restricted consumer search still requires authorized credential configuration. All DB changes gated and backup verified; replays inserted zero. Historical coverage, legacy processing, file serving and semantic classification remain open.
