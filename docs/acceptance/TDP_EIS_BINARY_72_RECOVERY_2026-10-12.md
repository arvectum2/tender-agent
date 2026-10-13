# Official EIS source binary recovery — 2026-10-12

- All **72/72** distinct public filestore attachment UIDs from **13 procurements** found in authoritative official EIS XML were re-fetched via bounded verified-TLS read-only HTTPS requests.
- SHA256 of each newly returned binary **and** its exact size both equalled the historical immutable original receipt: **72/72**, 0 unavailable, 0 mismatches, total **28,519,849 bytes**.
- The previous HTTP429 transport issue did not recur in this paced sequence. Download calls made no production writes, no TLS bypass, no retries upon errors and no bid/procurement actions.
- The other **96/96** official XML source items in the 20-case corpus had previously been verified from 17/20 authentic SOAP ZIP archives; 3/20 SOAP `no_data` remain UNKNOWN and are not fabricated as missing procurements.
- The 168/168 original file historical byte hashes remain verified; **72** original binary contents now have distinct fresh source re-fetch proof. No implication that five target resources are persisted in live Data Platform 0.6.0.
- Reproduce manifest-only technical receipt consistency without network by `PYTHONPATH=.:src python scripts/acceptance/verify_eis_filestore_receipts.py --source-audit /private/official-filestore-72-attachment-audit.json --verified-batch /private/bounded-filestore-verified72-private.json`. The verifier does not itself prove live transport or legal correctness.
- Private source audit manifest SHA256: `4f453e12c0013a200422990bf65a96fdfc476be6eda2b69065d18115391d9822`.
- Private fresh recheck manifest SHA256: `96a64d6d89f48478267bb2d976b241971f140ee2939e3478b82e3aef239acb82`.
- Raw original bytes, receipt URLs and private manifest are held on the authorized Mac mini under `evidence/tdp-r5/independent-20261012/`, never published.
- **Remaining R2 gate:** live production Data Platform lacks five selected target originals; isolated PostgreSQL/API 5/5 sources and 127/127 chunks are valid but not evidence of production ingestion. **R4 human-gold and R5 owner decisions: unapproved, 0/20.**
