# EIS SOAP vs original filestore: verified operational boundary (2026-10-12)

Scope: read-only investigation for Arvectum, not human R5 signoff.

- Current SOAP client get_docs_by_reestr_number authenticates against the official getDocsIP endpoint, downloads official XML notice ZIPs, not complete DOCX/PDF/XLS binary archives.
- Fresh read-only replay of 20 procurements 2026-10-12: 17 official SOAP ZIPs obtained, three no_data. 17 ZIP SHA256 unchanged since previous official snapshot. All 96 previous original notice XML files matched the official archives exactly.
- Intake extracts 72 source attachment UIDs from official notice XML. Original binaries are retrieved via a separate allowlisted EIS filestore URL and verified TLS downloader, with strict redirect limits.
- Historical cached 168 original files passed SHA256+length verification. The subset of 72 non-XML originals had source UIDs anchored to official XML. Cached byte integrity is proved, new official binary GET parity is not.
- Earlier independent filestore replay reported 24 HTTP404 and 48 unavailable transfers; a separate sampled attempt received HTTP429.
- New single read-only sample run against a real file UID of procurement 0372200172326000015 using actual current Python downloader returned HTTP429. Previously cached original was separately SHA256-confirmed. No new payload was received.
- Downloader already exposes HTTP429/404 as AttachmentTransportError(http_status:CODE), marks skipped with no stored_name and does not fabricate downloaded original. Four new 404/429 no-retry/no-fake-binary regressions pass.
- Previous authoritative evidence holds five saved original binaries for the above procurement, an official XML ZIP and a historical SHA256 receipt. A prior isolated non-production Data Platform replay persisted 5 originals and 127 chunks. Their persisted identity in the current production Data Platform has not been proved.
- Do not bypass rate limits, SSL, host allowlists, or claim full document completion when filestore downloads fail. Stop rapid retries on HTTP429, retain auditable SHA256 receipt, and arrange a later low-rate authorized recovery.
- Human procurement signoffs remain 0/20. Highest available archived edition is not independently verified current live edition. No production writes, bids, deployed changes, token alteration or watchdog change occurred.

See TDP_R5_INDEPENDENT_AUDIT_2026-10-12.md.
