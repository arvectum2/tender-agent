# APR-02 — explicit per-excerpt lot and revision binding

For RI223 223-FZ sourced document dossiers, a source registry number, document name and chunk ID confirm provenance but do not prove which individual lot or notice revision applies. Each excerpt now reports lot_number=UNKNOWN, lot_binding=UNVERIFIED, notice_revision=UNKNOWN and revision_binding=UNVERIFIED. The dossier reports revision_scope=DOCUMENT_REVISION_NOT_CONFIRMED. Multi-lot scope already uses UNRESOLVED_MULTI_LOT. The rendered review explicitly warns about both.

This change does not assign guessed bindings, merge different lot prices, infer effective amendment, establish requirements, supplier fit, risks or GO/NO-GO. Future binding requires authoritative, source-backed lot and revision links. Applied to RI223-only dossier; 44-FZ statutory logic and common RAG index unchanged.

Verification: 6 targeted document dossier tests passed; 533 Tender Research passed, 1 skipped; make check passed. No model changes or model comparison.
