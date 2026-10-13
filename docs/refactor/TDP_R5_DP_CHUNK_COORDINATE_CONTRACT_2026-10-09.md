# DP normalized chunk coordinate contract (R5 correction, 2026-10-09)

The previous initial Tender Agent projection misdescribed Data Platform chunk offsets as positions in the untrimmed extractor output. That was incorrect. Data Platform processing/chunking.py normalizes line breaks and whitespace with normalize_text, then creates chunk windows over THAT normalized text; each chunk text is also stripped at the boundaries. Thus char_start/end are NOT original PDF byte locations, source DOC/DOCX offsets or necessarily offsets within the original extracted text.

Consumer storage now labels chunk coordinate system as data_platform_normalized_text and preserves the original DP resource, document, chunk ID and SHA256 of each chunk TEXT only when consistent. The per-file metadata does not store original chunk text, because it may contain sensitive documents.

The source_quote_binding helper MUST receive actual per-chunk text directly from a trusted DP in-memory response / authorized retrieval and verify exact literal match and SHA256 hash. It reports only chunk-local start/end indices, NOT global normalized offsets. Any missing chunk text, hash mismatch, duplicate matching chunks, paraphrases, short quotes or bad source identities fails closed. It does NOT establish that the cited interpretation of the quote is legally correct.

R5 follow-up: add a source-authorized retrieval path for genuine per-chunk plaintext and original-document locator mapping; until then all LLM risks, requirements and commercial interpretations are explicitly marked unverified even if their strings occur inside a chunk.
