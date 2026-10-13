# R9 backup/restore diagnostic — 2026-10-12

R9 isolated backup+restore failed on Mac mini with Homebrew pg_dump/pg_restore 18.6 against PostgreSQL 16 disposable test service. Original error was hidden behind generic exit status.

Exact server rejection: `unrecognized configuration parameter "transaction_timeout"`; `Command was: SET transaction_timeout = 0;`. The setting is emitted by newer dump tooling and rejected on the older PostgreSQL server. This is a toolchain version mismatch, not proof of corrupt backups.

Verified corrective test environment: explicitly prioritize Homebrew PostgreSQL 16 executables:
```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$VIRTUAL_ENV/bin:$PATH"
python -m pytest -q tests/test_r9_backup_restore.py
```

Result: four pre-existing R9 tests PASS in 19.18s, using disposable test databases and isolated artifacts, production not modified. Added regression asserting CLI stderr remains actionable while database URL credentials are redacted from errors.

IMPORTANT: Do not change global Mac mini PostgreSQL client path, production databases or launchd services merely for the acceptance test. In CI use the PostgreSQL-client major version compatible with disposable test PostgreSQL server; if server changes, recheck compatibility.
