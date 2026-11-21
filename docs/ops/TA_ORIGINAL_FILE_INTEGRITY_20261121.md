# Original documents: verify actual bytes before tender analysis

**Status: isolated engineering candidate; not deployed.** Applies to the existing EIS 44-FZ/223-FZ document-store path and the RAG preparation/status checks. This is a concrete document reliability fix, not a new adapter or source-access grant.

## Reproduced failure mode

Before this patch the downloader silently counted a document as present if the SQL row said `downloaded`, without checking the file. A pending document could also be marked downloaded merely because a matching filename existed in its local cache. That could leave stale extracted text/chunks available for apparent readiness when original bytes were gone or replaced.

## New constraints

- Every previously downloaded file needs an existing regular file, pinned SHA-256, sane size and, when present, an exact recorded byte count. Missing, symlinked, unreadable or changed bytes are marked failed with `Original integrity failed: ...` and are **not retried automatically**.
- Reuse of a cached original requires an already pinned matching SHA-256 (and optional size). An unverified collision is refused rather than trusted or overwritten.
- New HTTP responses are bounded to configured maximum+1 bytes. Empty replies, unexpected hashes or known mismatched lengths are rejected. Completed bytes are fsynced to a temporary same-directory file, then published exclusively using a hard link; pre-existing files are never clobbered.
- RAG preparation stops before remote chunking/indexing when original integrity has failed; a former index with chunks cannot override this failure. The existing readiness/status projection reports `original_integrity` missing for known failed originals and avoids another Data Platform call for those failed cases.
- Historical and unverified URL availability, redirects, EIS revision linkage, 223-FZ document lists and externally signed manifests are **not** inferred by this check; verifying a hash stored locally does not independently authenticate who issued the file.

## Evidence and acceptance boundary

On base main `abcd8727`, synthetic original bytes (including mutated, missing, symlinked, conflicting cached, oversized, zero-length, mismatched source metadata and stale precomputed chunks) and existing RAR/DP path: **111 tests passed**, Ruff/diff check passed. No production database mutation, original fetch, ETP bid, credentials change, job replay or worker restart.

Before any live activation, review branch CI, source admission, data migration compatibility, current runtime PITR and rollback conditions under the existing AM-4/owner process. The three Nov 20 tender failures (two without document inventory, one with undownloaded original links) remain unresolved and must **not** be marked repaired by this code change.

## Durability across Data Platform outages (additional targeted fix)

The existing preparation flow previously flushed document download metadata but normally relied on later Data Platform processing to commit its SQL transaction. A platform processing error could therefore roll back a successfully downloaded original's persisted `local_path`, SHA-256 and status while leaving the actual bytes on disk. Preparation now commits source-file download results **before** opening the remote Data Platform client. A synthetic in-memory real-SQLAlchemy regression creates a pending EIS document, downloads the fake original, forces a Data Platform error, closes the processing session and verifies from a *new* session that the original's status, digest, length and bytes remain intact. Failure is reported as not ready; this does not fabricate a successful RAG result or launch an automatic retry.

## Direct analysis/API bypass closed

The ordinary `analyze_tender()` entrypoint, including the API and background job callers, previously checked a completed Data Platform index without consulting original-file integrity outcomes from preparation. For EIS-backed notices it now performs a **read-only recheck** of recorded original bytes, sizes and SHA-256 and refuses analysis before opening Data Platform if the inventory is absent, a linked document is pending, an original has disappeared/changed or a previously failed integrity verification remains recorded. It does not invoke a downloader, refresh EIS, mutate the database or delete stale vectors. Real archived 223-FZ originals are checked through the same EIS path. Synthetic direct-API tests verify no Data Platform call for tampered, pending, failed and absent originals; clean original bytes remain eligible. This is independent of source authorization and current revision binding.
