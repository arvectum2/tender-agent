# APR-02 — authentic RI223 multi-lot revisions and explanations (2026-10-08)

This is a read-only source projection, not a legal determination that the highest version is effective.

## Frozen original source (outside Git)
- Registry: **32616376947** (RI223 exact-number getDocsIP).
- Source ZIP on Mac mini: /Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/32616376947/documentation-archive.zip
- ZIP SHA-256: 840927b8dddba00cc682e78192ffb263cbd89d3fec1acbaba3fa60af63fd3575
- **Nine XML members:** three purchaseNotice revisions, six explanation members; all have exact registry binding.
- **Two lots, two positions** in the latest observed version.
- Two additional genuine multi-lot region77 samples 32616343061 and 32616347092 (2 lots each) appear in the frozen regional originals outside Git.

| Version | Source publication timestamp | Source submission-close timestamp |
|---|---|---|
| 1 | 2026-09-15T10:37:51 | 2026-10-01T16:00:00 |
| 2 | 2026-10-01T13:25:09 | 2026-10-12T16:00:00 |
| 3 | 2026-10-08T13:37:40 | 2026-10-20T16:00:00 |

Six explanation XML members each have a source-specific purchaseRegNum, question, dates, status code and document reference.

## Reproduced failure and bounded repair

Before: the authentic RI223 ZIP failed on unsupported XML root explanation, then would fail the existing single-notice-only guard. No multi-lot procurement or clarification content entered Tender Research.

After:
- Require exact RI223 XML root and matching purchase registry for notices and explanations, even when versions differ.
- Select the highest observed numeric version only if versions are unique and source publication/modification chronology is consistent; never infer legal effective status.
- Preserve all observed revision records, explicit deadline fields, lot counts, source XML member/hash/XPath, and modification descriptions.
- Keep lots and position evidence distinct; do not invent a notice-wide NMCK by summing individual lot prices.
- Preserve source clarification questions/status/timestamps and link their six published files to source provenance; source lot binding and legal meaning remain unknown.
- No old-version attachments are silently mixed with the selected source-version document set.
- Unsupported roots/namespace, wrong number, missing or nonnumeric versions, conflicting chronology, DTD, oversized XML/ZIP remain fail closed.

## Acceptance
- Exact original: version 3 projected, 2 lots, 2 positions, 6 explanations, 7 source-linked documents, notice-wide price UNKNOWN.
- Full model checks and CI are required. This is not full 223-FZ procedure/contract/outcome support or proof of ongoing publication validity.
