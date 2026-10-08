# APR-02 — source-bound opaque RAR acquisition (2026-10-08)

## Confirmed real-world gap
Public 223-FZ notice **32616445795** with OKPD2 **62.09.20.190** includes a RAR attachment that previously failed the attachment-extension allowlist. The original EIS RI223 SOAP request returned one document (3727_МИ.rar). Before the patch, the download status was incomplete_attachments / unsupported_extension.

## Frozen originals (not in Git)
Location: /Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08/32616445795/
- Original RI223 getDocsIP ZIP SHA-256: 65004d53a4d198857a192ad21052c95cfa7d812208c3ac6702324e42d7487de3
- Source XML projection: 1 lot, 0 observed protocols, no inferred procurement/legal status.
- Original RAR named 3727_МИ.rar: 3,606,714 bytes; SHA-256 36ef971be08ba1c4040e717239b78e464743542ee180f63bf37eb2ce79774241.
- After patch: 1/1 attached RAR downloaded, requires_manual_review=true, opaque_unparsed_count=1, content_analysis_complete=false.
- Local non-Git opaque-manifest.json records checksums, no SOAP token.

## Implementation and security boundary
- Reuse existing guarded attachment downloader (host/redirect/size/count/budget safeguards), with source-provenance-gated RAR support for RI223 only.
- Verify RAR4 or RAR5 magic header before saving; preserve the exact original bytes with SHA-256 and XML member/archive hash attribution.
- Never unpack or execute archive contents; downloaded does not mean parsed. Manifest explicitly reports UNINSPECTED_OPAQUE and requires_manual_review.
- All non-RI223 RAR and unknown extensions remain unsupported; no new 44-FZ path is enabled.
- Other unavailable or unsupported facts remain UNKNOWN/NEEDS_REVIEW. Not a legal conclusion, automatic participation decision or RAR extraction service.

## Verification
- Original live SOAP archive and RAR downloaded and hashed; 1/1 physical attachment, unparsed.
- 61 focused and integration-adjacent tests passed, 8 warning messages; make check and changed-core Ruff PASS, git diff --check PASS.
- Exact-head CI and attributable Owner REVIEW remain merge gates.
- APR-02 broader lifecycle/revision/clarification/real-multi-lot capability remains open and requires separate real evidence.
