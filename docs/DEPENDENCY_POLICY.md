# Dependency and compatibility policy

- Declare compatible dependency ranges in `pyproject.toml`; do not embed third-party package versions in application business logic.
- Commit resolved artifacts (`requirements.lock` with hashes for Tender Agent; `uv.lock` for Data Platform). Exact versions and hashes in these files are intentional, not harmful hardcoding.
- Update resolution with `uv pip compile pyproject.toml --extra dev --python-version 3.11 --universal --generate-hashes --output-file requirements.lock` (Tender Agent) or `uv lock --upgrade` (Data Platform), then reinstall into a **fresh** virtual environment and run the repository's CI-equivalent tests.
- Major upgrades, API contract changes and optional runtime/model backends require focused integration tests before promotion. A successful dependency resolver alone is not acceptance.
- Preserve SDK wire contracts and test the cross-repository consumer. Do not infer API compatibility merely from the server package version.
- Pin infrastructure major versions (Python runtime, PostgreSQL, Redis and container images) deliberately; upgrade them via their own migration/testing process. Floating production containers are unsafe.
- PostgreSQL acceptance backup/restore must use pg_dump and pg_restore from the same server major version. For the current PostgreSQL 16 acceptance container, invoke tests with a PostgreSQL 16 client first on PATH; a PostgreSQL 18 client caused pg_restore to fail when restoring to PostgreSQL 16. Do not globally override the Mac mini runtime client without checking other consumers.
- Track library-specific compatibility shims at the integration boundary. Remove obsolete shims only once the oldest supported version is no longer used.
- Security fixes should be backported if upgrading a major version is blocked. Never disable existing validation to make an upgrade pass.

## Validation gates

1. Lockfile regeneration has no unsupported dependency resolution.
2. Fresh-environment package install succeeds.
3. Ruff and repository full pytest pass (known skips reported).
4. Consumer SDK import and real source-evidence/report flow remain intact.
5. Optional browser, reranker, model and live EIS paths are separately marked **not verified** until their own tests pass.
6. CI results must correspond to the exact committed revision.
