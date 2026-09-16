# EIS ingest resilience

`INGEST-RESILIENCE-V1-001` hardens the existing `tender_research` ingestion path; it does not introduce a second acquisition stack and it never mutates EIS or another source.

## Durable restart contract

Registry-number ingestion accepts an optional `checkpoint_key`. When supplied, state is written atomically under `<data_dir>/ingest_checkpoints/`. The checkpoint binds the key to the source name, exact ordered input fingerprint, total item count, next item index, last source identity, status and last observable error.

A source item is committed to the database **before** the durable cursor advances. If the process stops after the database commit but before the checkpoint write, the item is replayed on restart; existing tender/document upserts make that replay idempotent. A checkpoint can only resume the exact same source and ordered input fingerprint. Reusing the same key for a different batch fails closed instead of guessing.

Use the existing CLI with a stable key for a bounded batch, for example:

```text
python -m src.tender_research.cli ingest-eis-registry-list --file data/eis_seed/registry_numbers.txt --checkpoint-key eis-2026-09-16
```

A completed checkpoint suppresses a second fetch of the same batch. Use a new checkpoint key for a deliberately new batch.

## Failure and recovery states

`in_progress` means the next index is safe to process. `completed` means every source identity in the bound input was processed or deterministically skipped. `blocked` records the failing source identity and error while leaving `next_index` on the uncommitted item. A later run with the same key reopens that item and retries from the durable boundary.

Transient source unavailability and missing credentials fail at the current item; they do not advance the cursor. `NO_DATA` is treated as a deterministic source result and advances. Any unexpected ingestion exception rolls back the current database transaction and leaves the checkpoint on that item.

## Revision-aware document identity

Existing `TenderRepository` identity/dedupe remains canonical. When EIS revision provenance is exposed, the stable revision tuple (`revision`, publication timestamp, revision source URL) becomes part of document identity. The raw provenance is preserved unchanged on the document row.

The same source document identifier in two different revisions therefore remains distinct when content differs. A SHA match across conflicting or incomplete revision scopes is **not** silently merged; it raises a document identity conflict for explicit reconciliation. Likewise, a stable revision identity cannot silently acquire a different content hash.

This complements the public 44-FZ active-revision binding: current analysis continues to use the active revision only, while repository ingestion cannot collapse conflicting historical/current source objects merely because another identifier or content hash happens to match.

## Operational boundaries

Recovery is read-only with respect to procurement sources. There is no bid submission, source-side update, external notification, benchmark mutation or fallback that discards provenance. Operators should inspect the checkpoint `last_error` and source state, then rerun the exact batch/key after the source is available. Ambiguous identity/revision conflicts require explicit review rather than automatic choice.
