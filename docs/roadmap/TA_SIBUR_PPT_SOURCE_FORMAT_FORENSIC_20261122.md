# SIBUR single-source .ppt vs saved OOXML slideshow — 22 November 2026

Task TA-SIBUR-PPT-SOURCE-FORENSIC-20261122; linked issue #686.
Scope is ONE historically saved first-party URL and its SHA-bound private
receipt/binary, not a new source download, conversion, document import,
Data Platform index, source-legal-original approval or production change.

## Independently verified facts

- Full original 27-page registry snapshot was replayed and SHA-verified
  using existing source_refs, yielding 516 original referenced URLs. Exactly
  ONE URL ends in .ppt and its archived file name ends in .pptx.
- The exact suspect reference is linked twice to verified original source
  rows, with receipt references matching the source snapshot. The file is
  saved as a SHA256-derived basename; its byte hash and exact 695,809-byte
  length match the historic archived receipt.
- Historic source URL suffix is .ppt. Historical captured MIME receipt is
  application/vnd.ms-powerpoint, and observed_format was recorded as pptx.
  This MIME string and URL suffix are NOT binary format proof.
- Actual saved file starts with ZIP/OOXML magic, not legacy OLE2 .ppt magic.
  ZIP integrity passes, content-types and main part are present, and
  /ppt/presentation.xml has ContentType
  application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml.
  Exactly eight PPT slide XML members exist.
- Therefore saved content is an OOXML PowerPoint slideshow package. The
  saved .pptx filename and source .ppt URL are both insufficient for
  claiming a legacy PowerPoint .ppt original; the internal slideshow type
  also differs from standard editable PPTX presentation main content type.

Saved source SHA256:
77277ab711c2b84a9ee220aab75873eb49c9931569ea2afe00fad2681b2f7f7f.
Source URL SHA256 (URI itself private):
61855643dd0c08fb1ebc82f8278c8e2a93eea0112f8e3ce883f57f66d03c8f33.

An independent immutable private audit receipt (mode 0600) was saved
without raw URLs or document contents:
SHA256 cf3f16c5cde02cde9589cd3c4b41ca02c5cec39140743005c9b2a39617c1dc3c.

## Explicit acceptance limits

This proves the **saved file content type and source-to-receipt identity**
from the historical snapshot. It does NOT prove WHY source URL and MIME are
legacy .ppt: publisher filename mismatch, source-side type conversion,
historical alias or download-time conversion cannot be distinguished from
this cached data alone. It does not independently re-check any current
official first-party revision or prove that the original was ever a
binary .ppt file.

Keep overall archive audit status NEEDS_REVIEW and source_original_ppt_verified
FALSE; quarantine this single ambiguous item. Do NOT silently rename saved
file to .ppt, fabricate an original, re-download all 516 saved files, ingest
this document in Data Platform or use it as a contractual source original.

Safe future gate: if the exact original is material to a procurement review,
obtain separately admitted read-only original source retrieval with original
URL, UID/version, timestamp, HTTP status, Content-Type and byte SHA and
independently inspect the retrieved bytes without overwriting historical
evidence. Otherwise the user-facing document review must remain UNKNOWN
for this attachment.

Implementation is a source-only offline one-file verifier with eight
synthetic negative/happy-path regression tests. No network, DB or production
write, customer information, bids or supplier messages.
