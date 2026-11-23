# Tender Agent runtime modernization — 2026-11-23

Status: Proposed staged candidate, NOT deployed.
Source baseline: arvectum2/tender-agent main b9f92bf3323f8e97c91296c3bbe81214df99d136.
Scope: only Tender Agent. Production and its Mac mini source worktree untouched.

## Compatibility contract

- Preferred runtime Python 3.15.2, minimum project support Python >=3.11.
- Universal requirements.lock dev and requirements-runtime.lock production
  use SHA-256 hash pins, latest compatible resolution via uv 0.13.9.
- Redis >=7,<8 (validated 7.4.1); pytest >=9,<10 (validated 9.2.0).
- FastAPI 0.165.0, Starlette 1.10.0, SQLAlchemy 2.1.9,
  Psycopg 3.3.9, Pydantic 2.13.5, pydantic-core 2.46.5,
  Ruff 0.17.6. Existing transitive Pydantic bound respected.
- CPython 3.15 requires Rust build of pydantic-core; macOS compiled with
  Rust 1.100.0. Docker isolates Rust toolchain in a builder.
- Keep the separate nonroot deploy/pilot Dockerfile frozen for independent
  reviewed migration; this PR modernizes main runtime Dockerfile.

## Verified Mac mini evidence

- Isolated Python 3.15.2 venv, dependency integrity uv pip check: PASS.
- Critical targeted regression: 115 passed / 2 skipped.
- Exact tokenizer test: 19 pass on 3.12 and 3.15 using sys.executable
  instead of a PATH-dependent bare python command.
- Version-stable AST-golden helper: 54 golden tests PASS on both
  3.12 and 3.15. Original approved SHA hashes never changed.
- Full candidate regression latest Redis7 / pytest9: 7029 PASS,
  292 skipped, 1 deselected, 7 subtests PASS. Log:
  staging/ta-runtime-modernization-20261123/full-candidate-py315.log.
- R9 backup/restore matrix test excluded ONLY from Mac local run:
  installed pg_restore 18.7 cannot restore into disposable PostgreSQL 16.
  Existing quality CI on ubuntu-24.04 explicitly pins the PG16 client.
  CI must execute that test; it is not waived.
- No production restart, tender submissions, EDS/signature actions,
  partner messages, schema migrations, or cross-product edits.

## New build and release gates

- Python 3.15.2-slim-trixie with Rust 1.100.0 builder stage only.
- Hash-pinned production-only runtime dependencies, no compiler in runtime,
  non-root UID 10001 as default runtime user,
  explicit pip check, preserve wv/libarchive-tools document converter.
- CI uv0.13.9 verifies both locks, Python3.15 quality runs with Rust and
  PG16 client; specialized Python3.11 CI jobs retain compatibility checks.
- A Linux ARM64 Docker build and no-network runtime smoke, plus all
  hosted CI/PG16 R9 and Redis integration jobs, must pass.
- No deployment until separate approved release window, current-state
  backup and safe rollback. Code PASS does not prove commercial readiness.
