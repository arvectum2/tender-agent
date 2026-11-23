# PRICE-01 — reviewed publication registry

The initial reviewed release is empty, revision 0. The legacy six-procedure
archive and client pins remain unchanged. The new case-scoped GET
/api/saas/company-portfolio/cases/{case_id}/reviewed-contracts requires the
historical and registry feature gates; default off. No public write API.

## Publication workflow

1. Obtain genuine originals in a separate research task. A trusted reviewer
   verifies the actual origin, contract status, complete scope, confidentiality,
   tax/price conditions and exact contracted quantities. Preserve original bytes
   privately; use the reviewed manifest format documented in the intake guide.
2. Independently approve the exact manifest SHA-256.
3. Run python -m scripts.price01.prepare_contract_registry_release with
   --release, --release-sha256, --action PUBLISH, --group-id, --reason,
   --manifest, --reviewed-sha256 and --originals. Redirect stdout to a new
   candidate file, not the existing release. The tool reruns original intake.
4. Review the candidate against the previously approved release: preserve its
   entire event prefix, check the new source review and public-safe fields
   (including scope, price terms and reason), then review an explicit code
   change to release.json and the compiled _RELEASE_SHA256. Do not accept
   an arbitrary self-computed SHA from a user. Repository review is the trust
   boundary; the chain is not a signature or independent authenticity check.
5. For withdrawal use the same tool with --action WITHDRAW, group ID, reason,
   existing release/pin; omit original and manifest arguments. A corrected
   replacement requires a fresh reviewed manifest and new group ID.

The offline tool never edits the published release or updates the compiled
pin. A release is bounded to 40 events/512 KiB. Chained event hashes, consecutive
revisions, immutable publication IDs and review pins, exact unit/range arithmetic
and no duplicate active procedure/contract/original are checked. Active group
ranges are never pooled, and equality of a target's registry number does not
prove target scope equivalence. API responses expose active groups and withdrawn
IDs/revisions, not private manifest notes, original bytes or original URLs.
Reviewers must ensure published scope/terms contain no private information.

A repository-pinned release is intentionally not a runtime-editable database;
publication or withdrawal requires reviewed release deployment. This is an
engineering workflow, not authorization to publish or deploy. No independent
signature, source authenticity, execution or completed quantity claims.

## Client pin update and acceptance

Web and iOS pin both the exact release file SHA and the SHA of the canonical public projection (without target-specific fields). When reviewing a new release, derive the public pin using reviewed_contract_registry.public_projection(load_release(raw, release_sha), release_sha) and sealed(); update both compiled client pins alongside the server release pin and run the client regression before deployment. Never accept a server-provided replacement pin without reviewed code/release changes.

Acceptance commands: run the Node cabinet flow, standalone Swift contract fixtures and Xcode XCTest, python -m scripts.acceptance.run_price01_postgres_tests (starts a disposable local private Unix-socket cluster, migrates it and cleans up), and scripts/acceptance/run_price01_browser_smoke.cjs with a local Playwright installation, PRICE01_PLAYWRIGHT_MODULE and PRICE01_CHROME if needed. Browser requests are intercepted; this is fixture-backed smoke, not a production or live-staging test.
