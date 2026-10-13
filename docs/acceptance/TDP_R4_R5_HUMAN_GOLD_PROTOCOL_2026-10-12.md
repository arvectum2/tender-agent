# R4 human gold and R5 independent owner review protocol — 2026-10-12

**Template only — zero human approvals.** Do not treat archived notices as proof of current auction status or replace owner decisions with model conclusions.

## Evidence-backed expert rubric

Each source reviewer independently validates: exact current notice revision and status; title and subject; original document SHA256 and citation locator; quantities and units; technical requirements; participant eligibility and restrictions; licenses and mandatory certifications; submission deadline and NMCK; contract security; delivery, acceptance, penalties and payment conditions. Every field needs a **VERIFIED / UNKNOWN / CONFLICT / NOT_APPLICABLE** label, exact original-file evidence and reviewer timestamp.

Record model ID/version, provider, input document set SHA, inference time, exact-quote correctness, unsupported-fact null accuracy, factual/semantic contradiction counts and provenance. A machine XML score is not human legal gold. Do not produce a signed GO, NO_GO or DEFER on the reviewer's behalf.

## Twenty original EIS cases

| # | EIS ID | Source triage | Current published revision reviewed | Original-document scope / citations | Eligibility and commercial terms | Human gold reviewer / date | Signed owner decision / evidence |
|---:|---|---|---|---|---|---|---|
| 1 | 0127100008626000013 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 2 | 0137200001226007700 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 3 | 0148200000526000028 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 4 | 0148300050426000047 | SOURCE_UNAVAILABLE | PENDING | PENDING | PENDING | PENDING | PENDING |
| 5 | 0149200002326001555 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 6 | 0158300034526000388 | STALE_RECEIPT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 7 | 0162300005826000156 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 8 | 0169300003326000181 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 9 | 0169300008226000223 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 10 | 0169300008226000225 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 11 | 0318200087026000163 | SOURCE_UNAVAILABLE | PENDING | PENDING | PENDING | PENDING | PENDING |
| 12 | 0348100024426000039 | STALE_RECEIPT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 13 | 0348100024426000052 | SOURCE_UNAVAILABLE | PENDING | PENDING | PENDING | PENDING | PENDING |
| 14 | 0349100009326000005 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 15 | 0349500000226000003 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |
| 16 | 0360600005326000018 | STALE_RECEIPT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 17 | 0372200172326000015 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 18 | 0376300000126000193 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 19 | 0377100005726000128 | HISTORIC_REPORT | PENDING | PENDING | PENDING | PENDING | PENDING |
| 20 | 0895100000126000897 | UNREVIEWED | PENDING | PENDING | PENDING | PENDING | PENDING |

## Machine-verified prior evidence and remaining gates

- Official EIS SOAP: 17/20 ZIP archives and 3 no_data; do not assert absence of a purchase solely from no_data.
- Three cached source notices were older than the highest archived official revision. Nine historical reports: initial prices matched 9/9, submission deadlines 7/9.
- 72/72 official binary attachment UIDs across 13 procurements were re-fetched with verified TLS, SHA256 and byte-size exact; 96/96 XML originals matched official ZIPs. Private original bytes and receipts remain on authorized Mac mini.
- Isolated authenticated DP/PostgreSQL HTTP source replay: 5/5 files and 127/127 normalized chunks correct. Target five originals were not found in the production-local DP collection audit; no production DP ingestion is claimed.
- Human R4 gold reviews and R5 owner signoffs remain **0/20**.

## Exit gates

1. Reproduce the five-original consumer flow in independent, disposable Data Platform staging with no connection to production port 8094, production credentials or production database. Record source receipt SHA, DP version and contract, resource/document/chunk identity, 127 chunk hash+offset checks and end-user report evidence.
2. Verify original document facts and legal obligations against independently human-labeled gold. Unsupported conclusions and conflicting revisions fail closed; mark UNKNOWN or DEFER and require review.
3. Record the 20 human source and commercial decision reviews with evidence and dates. Do not fabricate approvals or submit bids.
4. After genuine signoff, run exact-head CI and product report/API/PDF/DOCX acceptance; only then close the parent task.
