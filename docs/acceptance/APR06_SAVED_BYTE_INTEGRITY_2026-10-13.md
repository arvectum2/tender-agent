# APR-06 — Independent read-only stored-byte integrity audit (13 October 2026)

**Outcome: 168/168 archived manifest entries match exact original on-disk SHA-256 and byte lengths. This is a stored-file integrity check, NOT proof of current EIS status, completeness or human commercial approval.**

## Evidence boundary and method

- Original receipt manifest: `docs/acceptance/apr06_real_probe_receipts_2026-10-09.json`, `apr06-readonly-receipts-v1`, captured 9 October 2026. Original receipt SHA-256 strings and sizes are *compared against separately reread filesystem bytes*, not merely format-validated.
- Recheck at **2026-10-13T13:45:07+03:00**, on Mac mini in a disposable container with `--rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64`. A single existing artifact volume was mounted `:ro`; verifier script and manifest were mounted `:ro`; output was a new file under host `/tmp`. Existing preview/API/DB containers and their volumes were not modified by the checker.
- Reusable deterministic checker: `scripts/acceptance/apr06_saved_bytes_audit.py` with explicit size/hash, run-ID uniqueness and path/symlink protection; no document bytes, private filenames or secrets are committed.
- Machine-local output: `/tmp/TA-APR06-byte-hashes-20261013.json`. Report records cases, stored receipt counts, exact byte matches and non-approval flags. Original files remain on authorized Mac mini volume, outside Git.
- The `documentation-archive.zip` or extra local files are not represented as individually accepted source documents merely because they are scanned; the denominator is exactly the original `document_files` list in the receipt manifest.

## Verified historical byte counts

| Outcome | Count |
|---|---:|
| Historical receipt cases in manifest | **20** |
| Run directories found on mounted filesystem | **20 / 20** |
| Recorded original source documents | **168** |
| Recomputed exact SHA-256 **and** byte-size matches | **168 / 168** |
| Missing/mismatched recorded files | **0** |
| Cases containing at least one recorded file and all hashes matching | **17** |
| Cases with **zero** recorded source files | **3** |
| Independently verified latest EIS revision and complete attachment binding | **0** |
| Attributable human procurement reviews performed here | **0** |

The three zero-source archive entries are:

- `0348100024426000052` — zero recorded files
- `0148300050426000047` — zero recorded files
- `0318200087026000163` — zero recorded files

Do **not** count any of these three as a successful EIS ingest simply because their run directories exist. Of the 11 historically `docs_required` cases, **eight** had one or more source files already present and hash-valid; their completeness and analytical eligibility are still unverified.

### What the audit proves and does not prove

**Proves:** the exactly identified 168 historical source file byte sequences still exist in their respective saved run inputs and match the immutable 9 October hashes and sizes when reread on 13 October. This strengthens the archived evidence-inventory integrity baseline.

**Does not prove:** that those bytes originated from the authoritative *current* EIS edition; that the original EIS attachments are complete and correctly bound to a notice revision/lot; that the documents are legible, lawful or technically feasible; that any procurement remains open; that user/company eligibility, margin, citations or GO/NO_GO were reviewed; or that the APR-06 KPI gate was reached. The old manifest marks `official_notice_revision_verified_by_human=false` and `operator_reviewed=false`; these flags remain false.

## Reproduction on an authorized local copy

```sh
python -m scripts.acceptance.apr06_saved_bytes_audit \
  --manifest docs/acceptance/apr06_real_probe_receipts_2026-10-09.json \
  --runs-root /path/to/read-only/tender_operator_demo \
  --checked-at 2026-10-13T13:45:07+03:00 \
  --output /new/path/apr06-saved-bytes-audit.json
```

The output must not exist yet. The real run was performed with no network, a read-only artifact volume and separate temporary output; do not give a verifier write access to original source volumes.

**Next:** obtain current primary EIS notice edition and source-linked official attachments per candidate; focus on 11 `docs_required` cases and 223-ФЗ correct adapter; then independent procurement review of actual TЗ and owner KPI approval. No bids, ETP registration, signing, payment, model download or production deployment performed.
