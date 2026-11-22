# СИБУР — доказанная причина исторического пробела ID (22 ноября 2026)

Task TA-SIBUR-IMPORT-WINDOW-20261122, issue #692. This is read-only
reconciliation of *already saved* historical first-party source pages,
private import plans, original result receipts and a previously independently
verified PG16 working ID-set. No new source fetch or database mutation.

## Exact physical source/import lineage

- All 4,052 archived first-party pages and 48,536 source observations
  were independently SHA-replayed in PR #703 (protected main CI 19/19).
  There are 48,332 distinct exact archive external IDs.
- Separately verified 166/166 SHA-named **source input** JSON manifests
  in the 15-Nov archived import directory. Each matched the SHA256 in
  its own filename, and 166/166 result JSON receipts reference the exact
  input digest; each result older_rows_retained_privately equals the
  corresponding input older_rows. No changed source IDs or duplicate
  imported group IDs.
- These 166 manifests cover **4,047** original archived pages across
  categories 107, 108, 109, 112, 132, 999_08, 999_10, 999_11.
  They describe **30,081** distinct selected/imported group IDs,
  while **18,390** older historical source *observations* were retained
  privately and excluded. The 166 result receipts report exactly 30,081
  inserted, zero existing changed.
- A full independent original-page year analysis gives 18,420 pre-2024
  observations across all nine categories, of which exactly 30 belong
  to the ninth category 999_19. Thus the input older_rows total
  **18,390 exactly equals the pre-2024 observations of the eight imported
  categories**. Eight-category recent source observations are 30,087:
  six duplicates reduce them to 30,081 distinct imported IDs.
- The omitted support-services category **999_19** contains five
  saved original pages with **59** unique IDs, 30 published before 2024
  and 29 in 2024–2026. Those five pages and IDs were not in the 166
  preserved eight-category import manifests.
- Therefore the archived **18,251** distinct missing IDs are
  **18,222** from dates before 2024, and **29** later support-services
  category IDs. This matches exactly the protected #703 SHA-verified
  original-archive vs PG16 working proof.
- The independently verified **551** working-only IDs all come from
  separate saved source batch creation days 14-Nov (313) and 19-Nov
  (238); all 30,081 archive-overlapping working rows date from
  15-Nov import. The working PostgreSQL16 cluster is
  7694400479046774822, not production PG17.

## What this proves — and does NOT authorize

The recorded missing/extra ID membership is explained by explicit
archived import-window and category selection plus separately created
current registry batches. There is NO evidence of a sudden data deletion
or source corruption and no need to reimport blindly.

This does not establish that importing older historical records would
be legal, valuable or operationally safe. It does not prove the
truth/current legal status of any archived procurement. Source recrawl,
mass historical import, production changes, Data Platform indexing and
actual B2B trading remain unapproved.

Future separate Owner review must decide historical retention horizon,
value of older records and support-services category eligibility; any
write must separately pass full MI, backup/PITR/rollback, source
admission and staging tests. Issue #692 may be closed for the
**read-only historical discrepancy investigation** after protected
merge; a new explicitly approved implementation scope would be needed
for any actual data loading.

## Reproduction

Offline source-only CLI scripts/research/audit_sibur_import_window.py,
pointed to the previously saved private /categories/import directory,
verifies 166 SHA-named inputs, 166 linked receipts and exclusion counts.
No document payload or private identifier list enters the repository.
Negative/positive synthetic tests independently check source content
hash, exact receipt linkage, duplicates, symlinks, the eight-category
limit and older-row correspondence. Result is only historical evidence,
not a new source permission or an importer.
