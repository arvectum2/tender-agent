# TDP R5: Read-only inventory of saved EIS procurements

Date: 2026-10-09. Source: private Mac mini operator run metadata. Reproduce via scripts/ops/audit_tdp_eis_corpus.py with trusted runs root. No network requests or document-body reads.

## Structural findings

- Unique EIS procurements: 29
- Stored EIS runs: 46
- Structurally complete best runs: 10
- Best runs with report: 11
- Best runs with XML fact record: 1
- Best runs with recorded model invocation: 0
- Best runs with zero files: 8
- Best runs with originals but no report: 10
- Status distribution: {'docs_required': 18, 'needs_review': 5, 'completed': 1, 'completed_with_warnings': 5}

This measures FILE EXISTENCE and STORED METADATA only. It does not verify content accuracy, source quote correctness, OCR coverage, legal risks, financing, unsupported UNKNOWN fields, human sign-off or completeness of original tender documentation. A completed run status is not business acceptance. No quality percentage may be inferred from these counts.

Next: retrieve missing permissible EIS originals, preserve exact chunk IDs and offsets, and verify >=20 individual source-locked procurement claims against human-reviewed truth. Owner Safari quality gate remains pending. No external procurement submissions.

## Selected representative run per unique registry number

| Registry | Originals | Text marked extracted | Report | XML record | Status |
| --- | ---: | ---: | :---: | :---: | --- |
| 0127100008626000013 | 6/6 | 0 | no | no | docs_required |
| 0137200001226007700 | 8/8 | 8 | yes | no | needs_review |
| 0148200000526000028 | 7/7 | 0 | no | no | docs_required |
| 0148300050426000047 | 0/0 | 0 | no | no | docs_required |
| 0149200002326001555 | 5/5 | 0 | no | no | docs_required |
| 0158300034526000388 | 14/14 | 14 | yes | no | needs_review |
| 0162300005826000156 | 18/18 | 18 | yes | no | completed |
| 0169300003326000181 | 16/16 | 16 | yes | no | completed_with_warnings |
| 0169300008226000223 | 12/12 | 12 | yes | no | completed_with_warnings |
| 0169300008226000225 | 12/12 | 12 | yes | no | completed_with_warnings |
| 0318200087026000163 | 0/0 | 0 | no | no | docs_required |
| 0348100024426000039 | 19/19 | 10 | yes | no | needs_review |
| 0348100024426000052 | 0/0 | 0 | no | no | docs_required |
| 0349100009326000005 | 5/5 | 0 | no | no | docs_required |
| 0349500000226000003 | 4/4 | 0 | no | no | docs_required |
| 0360600005326000018 | 8/8 | 0 | no | no | docs_required |
| 0372200172326000015 | 6/6 | 6 | yes | yes | completed_with_warnings |
| 0376300000126000193 | 8/8 | 8 | yes | no | needs_review |
| 0377100005726000128 | 13/13 | 13 | yes | no | completed_with_warnings |
| 0895100000126000897 | 7/7 | 0 | no | no | docs_required |
| 32615850735 | 0/0 | 0 | no | no | docs_required |
| 32616045143 | 1/1 | 0 | no | no | docs_required |
| 32616197376 | 0/0 | 0 | no | no | docs_required |
| 32616263956 | 0/0 | 0 | no | no | docs_required |
| 32616369437 | 0/0 | 0 | no | no | docs_required |
| 32616401070 | 0/0 | 0 | no | no | docs_required |
| 32616412768 | 1/1 | 0 | no | no | docs_required |
| 32616416057 | 3/3 | 0 | no | no | docs_required |
| 32616450723 | 2/2 | 2 | yes | no | needs_review |

All procurement IDs are public registry numbers. No raw contracts, personal information or original customer details are included.
