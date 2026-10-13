# R3 safety gate before decomposing historical run binding backfill

Task: TDP-REFACTOR-20261009. Scope: src/modules/customer_pilot/legacy_binding_backfill.py.
This document is an implementation-boundary and test-plan note, not evidence
of successful production migration.

Current legacy binding backfill accepts a complete immutable historical
snapshot only. It must never invent, repair or widen source identity.

## Non-negotiable invariants

1. Same customer/project/case/run/result/artifact identifiers across all
   inputs. A mismatched tenant returns CONFLICT before ORM changes.
2. Keep the PostgreSQL row-lock order: result first, artifact second, and
   populate-existing semantics for both locks. Avoid race-induced dual writes.
3. Reject partially preexisting source bindings. Fully already-verified
   bindings must be independently revalidated; never blindly skip.
4. Require exactly the canonical snapshot file set and reject symlinks,
   non-regular files, missing/extra files and hash or manifest mismatches.
5. Verify canonical report and final PDF generation identity, content hashes,
   source graph hash, report model hash and policy versions **before** assigning
   mapped ORM values.
6. Preserve ownership of the external transaction: the function does not
   commit or issue a blanket rollback; its caller is responsible for rollback
   if flush or post-flush verification fails. A returned CONFLICT after a DB
   flush failure is **not** evidence the DB session is reusable.
7. Never write a source snapshot, upload a document, change live DP storage,
   or silently remediate an invalid historical artifact during backfill.

## Verified tests

The original three tests cover valid backfill/idempotence, missing manifest,
and conflicting legacy report hash.

Additional tests in tests/test_r8_legacy_binding_backfill.py cover:
- cross-tenant ownership mismatch and no ORM mutation;
- partially preexisting binding and no automatic repair;
- unexpected file in canonical snapshot directory;
- symlink to a real external requirements.json file;
- simulated ORM flush error with **in-memory** field restoration (not a
  transaction-level rollback guarantee).

Next R3 decomposition should first extract pure preflight identity projection
or narrow path safety helpers, keep public signature and runtime DB transaction
boundary stable, preserve AST parity or compare domain-level outputs, run
focused full regression and exact-head CI. Only after these gates may the
large main function be restructured. This safety baseline does NOT close R2
live target data provenance, R4 human-gold benchmark or R5 owner acceptance.

## Staged legacy facade extraction (2026-10-11)

The original 266-line backfill_legacy_run_binding implementation now lives in
legacy_binding_backfill_orchestrator.py as run_immutable_backfill, with its
original Python function body AST SHA256:
d6fe9df602e3726563d4996a4beea851923f2c3fece2cfe1755eddd913b20b30.
The legacy public facade signature remains stable and injects 16 original
runtime dependencies to preserve patch points and module ownership.

The two deliberately broad exception handlers and redundant tuple conversion
are suppressed only within the extracted module in Ruff, pending a future
separately justified behavior-preserving cleanup. The original transaction,
ownership, filesystem, source-graph and immutable-artifact semantics were not
modified. Focused safety tests: 10 passed. Full local regressions: 3792 passed,
238 skipped, 1 known unrelated R9 pg_restore test deselected. Exact-head CI and
pull-request merge are still required before marking this stage integrated.

## Subsequent identity projection split (2026-10-11)

A pure, read-only 36-line block computing expected_base, identities and
expected_manifest was extracted from the long stateful backfill orchestrator
into legacy_binding_manifest_projection.py. All three original assignment AST
nodes are unchanged, combined SHA256:
563caa2528d86cd307850dfac24128a4d4f616791faff5e1d8a3b65e309cb24c.
The remaining orchestrator body AST after the controlled split is fixed
as 101bae796279b928c9ffeb69287b8cf44bc9657fff8768fc478a1064b08e9dc0,
rather than misleadingly claiming the original whole 266-line body is still
byte-for-byte in the new orchestrator. The lock/tenant/file checks and all
subsequent mutation/flush/rollback responsibilities remain in the orchestrator.

Pure helper tests assert the original assignment AST and sample tenant scoped
storage keys, model hash and immutable source graph mapping. The original
fail-closed backfill, idempotent checks and runtime facade remain exercised
by the R8 legacy backfill tests. Extraction does not rewrite or repair any
production storage and is gated on exact-head GitHub CI before merge.
