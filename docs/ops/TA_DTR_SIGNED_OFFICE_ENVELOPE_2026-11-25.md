# DTR signed office envelope incident — 25 November 2026

Scope: source-only fix of one failed item in the 25-Nov daily run
DTR-20261125T050005Z-cd0a5087. No current EIS fetch, production API call,
database mutation, inference, deployment or DTR replay.

## Confirmed failure

Read-only production query returned one FAILED item, registry
0187200001726001774, persisted stable code source_or_index_not_ready:failure,
no analysis. The existing local runner log identifies the exact cause:
unexpected content in signed DOCX ZIP. Five source originals were downloaded
and independently matched registered size and SHA256; all five had extraction
pending, zero local chunks. Four envelopes contain DOCX, SIG and named PDF
companion; one contains XLSX, SIG and named PDF companion. All SIG names bind
to the corresponding office member; the PDF name is exactly the office member
name plus .pdf. Signature authenticity and semantic equivalence are unproven.

## Source correction

- Constrained, size-bounded signed DOCX/XLSX envelopes, exactly one expected
  office member, associated signature(s), optional single explicitly named PDF.
  Preserve old strict DOCX-only recovery wrapper; refuse unexpected files,
  invalid office/PDF signatures, unsafe entries, missing signatures and
  source hash mismatch. Never modify or unpack originals in place.
- Send the office and companion to the document-processing boundary separately
  with independent content-bound canonical URIs and receipts. Project both
  member texts in the normalized coordinate space used by Data Platform
  chunking. Keep member-level resource/document/chunk identities, SHA and
  coordinates. Deduplicate only identical chunk hashes/text while retaining
  all member references. No claim PDF and office contents are equivalent.
- Verify member receipt identity, nonempty extraction/chunks, text hashes,
  normalized source spans, combined text limit, no reported truncation or
  unresolved PDF pages. A projection exception rolls back the local DB
  transaction and stops preparation before indexing stale chunks. Existing
  original receipts and current EIS verification gates remain mandatory.

## Verification

130 affected tests PASS, Ruff PASS, git diff --check PASS. Includes old DOCX
contract, PDF/XLSX combinations, identical vs distinct content, unexpected or
unsafe members, bad source hash, missing/foreign member receipt, unresolved
pages, truncation, incorrect chunk span, and stale-index readiness refusal.
Real read-only smoke with database-registered SHA: 5/5 envelopes verified;
all original bytes unchanged, 0 production extraction updates.

Independent local offline execution of the installed DP e4fdda34 extraction/
chunking code, with no OCR or vision provider, on all ten document members:
10/10 returned nonempty extracted text and chunks; 10/10 chunk hashes and
normalized source spans verified. Individual chunk counts total 235 before
cross-member deduplication. One page of the XLSX companion PDF was flagged
unresolved by native-text extraction. No OCR/LLM, API call, persistence or
customer data publication. This is an extraction-only smoke, not an accepted
analysis or proof of PDF page coverage. The new guard appropriately refuses
such a partial receipt until a complete extraction is demonstrated.

## Remaining gates

Actual recovery of this specific failed item requires approved current source
revision/inventory, bounded targeted repair admission and host capacity,
verified complete PDF extraction (including the flagged page), exact index
and evidence checks, then human review. Do not replay the full DTR or
manually promote the failed row. Production remains unchanged. This source
fix does not establish verified signature authenticity or current EIS status.
