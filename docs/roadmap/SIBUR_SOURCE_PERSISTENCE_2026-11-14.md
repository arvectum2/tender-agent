# Source-separated SIBUR registry persistence — 2026-11-14

Owner authorized writing verified data into the working Tender Agent database on 2026-11-14. This is separate from AM-4 and grants no autonomous bidding, payment or external mutation.

Use existing procurement_tenders; unique (source, external_id), platform_name and platform_url. No new schema or deal creation. Keep source identifiers distinct: sibur_public for public SIBUR registry, separate namespaces for authenticated SAP SRM if needed, B2B-Center, ETP GPB, TEK-Torg, EAT and Moscow supplier portal when each connector is verified. No cross-platform merging on identifier alone. Existing EIS and PQ collection paths are unchanged.

Preflight: MI internal APFS acceptance PASS; full backup of active TA arvectum_local verified with PG16 pg_restore -l before write, checksum 4b5973172988742784c337212a0f3d33f7ead4d5fa031e5fee9a719e51b12979. All 27 original source pages replayed by SHA and exact normalized equality. Imported 313 unique procedures, 314 observations, source sibur_public. Final repeat import with PostgreSQL RETURNING inserted 0 and verified all 313 content hashes; independent counts confirm 313 distinct external IDs and 314 observations. No other source rows changed. The initial driver rowcount was unsupported (-1); corrected to RETURNING.

Date-only publication is stored at UTC midnight as a storage convention, not a claimed publication instant. Deadline raw text is retained but no timezone is invented. Organizer is preserved in observations, not silently represented as legal contracting customer. Attachment references remain references; 2 sampled originals were verified earlier. On differing observed hashes the insert-only probe fails closed rather than overwriting data. Incremental revision reconciliation remains a separate implementation stage.

Next: integrate canonical historical observation persistence, authorized document retrieval and Data Platform indexing, verify source coverage, then GEH and small-volume procurement discovery. Do not change the running container image until its deployment gate is reviewed separately.
