"""Disposable PostgreSQL acceptance runner; it never uses deployment Compose."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "tests/integration/compose.r8-postgres.yml"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(*args: str, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def main() -> int:
    project = f"r8pgtest{secrets.token_hex(4)}"
    temp_root = Path(tempfile.mkdtemp(prefix="r8-pg-acceptance-"))
    env = os.environ.copy()
    password = "test-" + secrets.token_urlsafe(18)
    port = str(_free_port())
    env.update(
        {
            "R8_POSTGRES_PASSWORD": password,
            "R8_POSTGRES_PORT": port,
            "RUN_R8_POSTGRES_INTEGRATION": "1",
            "AI_CORP_DATABASE_URL": f"postgresql+psycopg://r8_acceptance:{password}@127.0.0.1:{port}/r8_acceptance",
            "AI_CORP_ARVECTUM_DATA_DIR": str(temp_root / "data"),
            # Disposable schema downgrade fixture must remain empty of
            # canonical learning evidence. Production defaults ON, but
            # this test specifically destroys/recreates migration 107.
            "TENDER_LEARNING_CAPTURE_ENABLED": "0",
        }
    )
    (temp_root / "data").mkdir(mode=0o750)
    compose = ("docker", "compose", "-p", project, "-f", str(COMPOSE))
    result = 1
    try:
        _run(*compose, "up", "-d", "--wait", env=env)
        _run(sys.executable, "-m", "alembic", "upgrade", "head", env=env)
        _run(
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration/test_r8_postgres_artifact_concurrency.py",
            env=env,
        )
        _run(
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration/test_r9_postgres_publication_concurrency.py",
            env=env,
        )
        # Exercise the actual R8 schema round-trip on the same disposable
        # PostgreSQL service.  Migration 096 backfills the legacy report hash
        # before restoring the old NOT NULL contract.
        _run(
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "095_add_r8_current_run",
            env=env,
        )
        _run(sys.executable, "-m", "alembic", "upgrade", "head", env=env)
        _run(sys.executable, "-m", "alembic", "upgrade", "head", env=env)
        result = 0
    finally:
        subprocess.run((*compose, "down", "--volumes"), cwd=ROOT, env=env, check=False)
        shutil.rmtree(temp_root, ignore_errors=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
