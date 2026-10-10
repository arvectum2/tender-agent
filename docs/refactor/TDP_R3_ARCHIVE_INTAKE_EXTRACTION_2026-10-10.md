# R3: isolated safe ZIP intake for Tender Agent

The legacy upload_service_legacy.py mixed ZIP archive inspection, upload state,
Data Platform document processing, supplier economics and report generation.
The archive reader is now a pure, bounded adapter in operator_archive_intake.py.
It delegates extracted file text to the same existing Data Platform consumer via
an injected callable, and returns the same AnalyzedDocument format to legacy code.

Security and compatibility:
- no entry is written to disk;
- old max entry-count and total uncompressed-byte limits remain enforced;
- POSIX/Windows unsafe paths, symlinks, duplicate case-insensitive entry names
  and recursively embedded ZIP files are rejected or skipped;
- encrypted, unreadable or corrupted entries produce explicit review warnings;
- original upload_service_legacy._extract_zip_documents signature stays stable;
- no OCR/LLM code duplicated and no external submission.

Nine ZIP-specific tests (including existing legacy tests) and 33 broader
operator-upload/source-report regressions passed locally. A schema-valid LLM
result is still not a proven original source. Source quote and human quality
acceptance remain separate gates of canonical TDP-REFACTOR-20261009.

No change to owner private preview ports 18082/18083 or existing run data.
