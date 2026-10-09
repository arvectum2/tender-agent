# APR-02 / ARV-006 — RI223 source-bound lots, positions and protocol observations

Date: 2026-10-08. Scope: **bounded read-only XML-source projection**, not complete 223-FZ procedure automation.

## Frozen original evidence

Authoritative originals, out of Git: `/Users/master/arvectum-runtime/eis-223fz-corpus/2026-10-08`.
Provenance and full archive SHA-256: `APR02_RI223_SOAP_VERIFIED_2026-10-08.md` and original local `manifest.json`.

| Procurement | RI223 original XML notice | Source lot / position | Separate protocol XML | Source-bound total notice + protocol file links |
|---|---|---|---|---:|
| 32616444788 | purchaseNotice | 1 / 1 | NOT_OBSERVED | 4 |
| 32616445632 | purchaseNotice | 1 / 1 | NOT_OBSERVED | 2 |
| 32616445866 | purchaseNotice | 1 / 1 | purchaseProtocol (1 XML member) | 2 |
| 32616447910 | purchaseNotice | 1 / 1 | purchaseProtocol (1 XML member) | 2 |

**Correction to the earlier snapshot:** protocol artifacts were indeed available in two downloaded SOAP ZIPs as distinct `purchaseProtocol` XML members. They were not present as elements in the `purchaseNotice` XML documents themselves. This is a change to observation coverage, **not** authorization to infer award/completion statuses.

Observed exact XML paths:
- `/purchaseNotice/body/item/purchaseNoticeData/registrationNumber`
- `/purchaseNotice/body/item/purchaseNoticeData/lots/lot/lotData/lotItems/lotItem`
- `/purchaseNotice/body/item/purchaseNoticeData/attachments/document`
- `/purchaseProtocol/body/item/purchaseProtocolData/purchaseInfo/purchaseNoticeNumber`
- `/purchaseProtocol/body/item/purchaseProtocolData/attachments/document`

Source values: `ordinalNumber`, `subject`, `initialSum`, `okpd2/code`, `okpd2/name`, `qty`, `okei/code`, `okei/name`, protocol `registrationNumber`, `typeName`, `status` code and `version` code. **No canonical lifecycle statuses or legal conclusions are derived** from raw `status=P` or SOAP transport `completed`.

## Implementation boundary

- `src/tender_research/providers/ri223_soap_evidence.py`: guarded ZIP+XML parser; exact registry binding, one unambiguous notice version, per-record member SHA-256, archive SHA-256 and source XPath; source-bound notice/protocol links.
- `RealEisLoader.fetch_by_registry_number(..., law_type="223fz")`: explicit RI223 SOAP selection and allowlisted existing ZIP transport. `EisTenderLoader` and `TenderResearchPipeline.ingest_eis_by_registry_numbers(..., law_type="223fz")` expose the same bounded opt-in; discovered 223-FZ items also request the 223-FZ path rather than generic PRIZ.
- Normalized procurement retains raw evidence in existing `raw_payload`/document metadata; no competing DB, legal engine, benchmark truth or private ETP action.
- 44-FZ default remains PRIZ and existing loader semantics remain unchanged. For 223-FZ, missing documents **must not invoke legacy listAttachments**.
- Duplicate notice versions, malformed or oversized ZIP/XML, unrecognized namespaces, cross-registry notice/protocol linkage and unsupported status semantics fail closed. Multi-lot parsing is covered by a sanitized *synthetic* regression but is **not claimed as verified real-source coverage**.

## Boundaries still open

- Real multi-lot/multi-position layouts; revisions and amendment ordering; clarifications, cancellations and contract/award transitions; procedure-specific legality; cross-region completeness and RAR policy.
- No autonomous GO/NO_GO, procurement submission, electronic signing, external communication, payment or production mutation.

## Acceptance

- Four original archive SHA-256 checks + 4/4 notice parse, 1 lot and 1 position each, 2/4 protocol observations, and 10 source-bound notice/protocol attachments.
- Synthetic positive/negative regression suite includes missing protocols, multi-lot source branches and fail-closed ambiguous/mismatched inputs.
- Owner REVIEW required for merging; broader APR-02 outcome remains open.
