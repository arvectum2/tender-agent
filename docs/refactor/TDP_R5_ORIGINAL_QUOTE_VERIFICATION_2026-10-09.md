# R5: original-file source quote attestation

This is a conservative product-domain capability, not a claim-verification agent or source-of-legal-truth engine.

The private authenticated Operator Workspace endpoint is:

POST /api/demo/tender-agent/workspace/runs/{run_id}/verify-quote

JSON body: {"file_id":"FILE-04","exact_quote":"...20 to 800 characters..."}

Validation: one original file must already belong to the authorized run; the supplied saved filename must resolve directly inside that run's input directory, without symlinks or traversal. Original file must be <=12 MiB and its SHA256 must match its saved canonical_uri. The process_document consumer endpoint of Data Platform is **non-persisting** (unlike ingest_document) and is called with the original bytes, collection ID and chunking options. Real resource ID, document ID, canonical URI, extraction status, chunk ID/hash and exact extracted chunk text must agree with the originally saved source metadata. Quote must occur literally and uniquely within exactly one validated chunk. A matching response only proves **literal text found in reprocessed source**. Original PDF page, DOCX paragraph, business risk or legal interpretation are NEVER asserted.

Missing source metadata, stale originals, unsupported or unsafe filenames, unavailable DP processing, short/paraphrased/ambiguous quotes all yield no source claim. Endpoint is protected by the same private pilot Basic Auth middleware and configuration gate as existing Operator Workspace; the API does not store or forward quotes outside the private DP process API, send messages, or change procurement runs.

Verified on actual EIS registry 0372200172326000015 stored DOCX (FILE-04) in isolated Mac mini stage: resource/document identity and 31 chunk hashes reproduced; a literal 250-character original excerpt obtained an exact matching chunk; a fabricated sentence was rejected. No document text was printed in diagnostics.

This only adds a manual verification primitive. Model output presently contains unverified free-form requirements/risks; no automatic mapping or business/legal promotion is performed. R5 next needs a typed quote-bearing model schema, source-scoped statement attribution, >=20 source-locked human truth-evaluated 44/223-FZ cases, and owner visual acceptance. Keep existing owner pilot 18083 unchanged until gate.
