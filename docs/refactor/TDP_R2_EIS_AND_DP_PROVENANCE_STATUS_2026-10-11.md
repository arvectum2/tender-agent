# TDP R2: Official EIS XML / existing Data Platform verification

Task: TDP-REFACTOR-20261009. This is a source audit, **not** production acceptance.

## Results confirmed on Mac mini, October 11, 2026

- Original procurement: 0372200172326000015. Direct official int.zakupki.gov.ru verified TLS and an authorized, read-only getDocsIP SOAP request returned completed. No TLS bypass or proxy used.
- Official ZIP: 17,041 bytes, SHA256 35978ce41fc87955491cc53705b0bd126c6d8217b82134e640eed1d78ed9e500. It contains one XML notice (epNotificationEZK2020), SHA256 ed5c742b554913c65d9001b658aa23619df418b2d19e6f6d6754a1bc70141bba. Its commonInfo/purchaseNumber is the requested procurement and enclosing versionNumber is **1**. Edition observed at query time only.
- All five earlier public attachment UIDs were found in the official XML. SHA256 of five cached original binaries matches five previously independently recorded public receipts (5/5), but XML UID membership is not itself an attachment-byte hash attestation.
- Current Data Platform source, run in an isolated non-production replay, ingested 5/5 originals; resource/document stable-ID and binary-hash reconciliation passed 5/5; 127/127 chunk text digests and normalized text character ranges matched.
- Authorized, read-only running DP 0.6 GET export surveyed 24 collections and 2,034 persisted resources without error. **No** stored target attachment resource was found by canonical URL, original SHA, procurement number or five UIDs. All five public receipts lack persisted DP IDs. **Target-specific live provenance is not confirmed.**
- A **different** live EIS-linked DP resource verified 41/41 stored normalized chunk offsets and 41/41 content hashes using authorized include_content=true export. This checks working DP normalization, not provenance of the five target originals.
- R4 local model smoke tested one short source quote from public EIS (Gemma 4 12B 1/1 compliant under JSON schema; Qwen2.5 3B and Qwen3 4B did not satisfy literal-quote constraints). Not a human-gold benchmark.
- R5 queue has 20 procurement rows/168 file identities, but **zero verified human signoffs**. Generated GO/NO-GO must not be treated as accepted commercial decisions.

## Operator continuation

1. Use an isolated non-production API fixture or locate previously stored original DP records. Do not modify production or seed data as a real imported tender.
2. Match independently obtained bytes against persisted resource/document/chunk IDs with strict normalization/URI/revision checks.
3. Create human-gold R4 evaluation and obtain independent human R5 review for at least 20 original procurement cases. Missing facts remain UNKNOWN.

Read-only evidence stays on authorized Mac mini under:
/Volumes/ArvectumSSD/Arvectum/evidence/tdp-r2/0372200172326000015-20261011/.
This GitHub document includes no tokens, signed archive URLs, raw customer text or attachment binaries.
