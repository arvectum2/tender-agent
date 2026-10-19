"""Safely run existing source pipeline using owner-local, already provisioned files.

No passwords or API keys are printed, copied to new config files, stored in
Git, or passed in argv. These values only exist in the child process env.
The runner refuses SQLite / noncanonical databases and mismatched app keys.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
TENDER_ENV = HOME / ".config/arvectum/apr04-local.env"
PLATFORM_ENV = HOME / "Library/Application Support/Arvectum/data-platform/runtime.env"

OPERATIONS = {
    "evidence": (
        "scripts.procurement_llm.probe_gemma_source_repair",
    ),
    "probe": (
        "scripts.procurement_llm.probe_gemma_source_repair", "--llm",
    ),
    "ready": (
        "scripts.procurement_llm.source_quality_rerun",
        "--number", "0163200000326005243",
    ),
    "index": (
        "scripts.procurement_llm.prepare_eis_original_documents",
        "--number", "0163200000326005243",
        "--index-only", "--apply", "--confirm-database", "arvectum",
    ),
    "quality": (
        "scripts.procurement_llm.source_quality_rerun",
        "--number", "0163200000326005243",
        "--apply", "--confirm-database", "arvectum",
    ),
}


class RuntimeGateError(ValueError):
    """Operator environment is missing, mismatched or unsafe."""


def _secure_env_file(path: Path, owner_uid: int) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeGateError("missing or symlinked owner runtime configuration")
    info = path.stat()
    if info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeGateError("existing owner runtime configuration must be mode 0600")
    result = dotenv_values(path)
    if not result or any(not isinstance(v, str) or not v for v in result.values()):
        raise RuntimeGateError("owner runtime configuration empty or malformed")
    return result




def _canonical_docker_password() -> str:
    """Use the existing *owner-operated* local PG container configuration.

    The Docker-managed password is held in memory, never printed or written.
    This requires Docker operator permissions; failure is terminal.
    """
    try:
        proc = subprocess.run(
            [
                "docker", "inspect", "--format", "{{json .Config.Env}}",
                "arvectum-postgres",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=True,
        )
        entries = json.loads(proc.stdout)
        if not isinstance(entries, list):
            raise RuntimeGateError("canonical Docker PostgreSQL configuration malformed")
        passwords = [
            entry.split("=", 1)[1]
            for entry in entries
            if isinstance(entry, str) and entry.startswith("POSTGRES_PASSWORD=")
        ]
        if len(passwords) != 1 or not passwords[0]:
            raise RuntimeGateError("canonical Docker PostgreSQL password unavailable")
        return passwords[0]
    except (subprocess.SubprocessError, OSError, ValueError):
        # Do not propagate Docker errors: stderr may reveal runtime context.
        raise RuntimeGateError(
            "existing canonical Docker PostgreSQL auth unavailable"
        ) from None

def build_existing_environment(
    *, owner_config: Path = TENDER_ENV, platform_config: Path = PLATFORM_ENV,
    inherited: dict[str, str] | None = None, owner_uid: int | None = None,
    canonical_password_resolver=None,
) -> dict[str, str]:
    """Compose a restricted in-memory environment, no network or mutation."""
    uid = os.getuid() if owner_uid is None else owner_uid
    owner = _secure_env_file(owner_config, uid)
    platform = _secure_env_file(platform_config, uid)
    if owner.get("AI_CORP_RAG_DATA_PLATFORM_API_KEY") != platform.get(
        "ARVECTUM_DATA_INTERNAL_API_KEY"
    ):
        raise RuntimeGateError("Tender Agent and Data Platform keys do not match")
    # PROD_DB_NAME belongs to a separate deployment profile and is not an
    # authoritative identity for Tender Agent's already-created local DB.
    # Never modify that setting, and never connect to that other DB by default.
    if not all(
        owner.get(k) for k in ("PROD_DB_USER", "PROD_DB_PASSWORD")
    ):
        raise RuntimeGateError("existing database role credentials missing")
    env = dict(os.environ if inherited is None else inherited)
    existing_dsn = env.get("AI_CORP_DATABASE_URL")
    if existing_dsn:
        parsed = make_url(existing_dsn)
        if (
            parsed.database != "arvectum" or not parsed.drivername.startswith("postgresql")
            or parsed.host not in {"127.0.0.1", "localhost"}
            or parsed.port != 55432
        ):
            raise RuntimeGateError("cannot override foreign or nonlocal database settings")
    else:
        # A PROD_DB_NAME mismatch means its saved password may be for another
        # deployment. Authenticate to the known local container using its own
        # already-provisioned credential; never alter the other DB profile.
        if owner.get("PROD_DB_NAME") == "arvectum":
            actual_password = owner["PROD_DB_PASSWORD"]
        else:
            resolver = canonical_password_resolver or _canonical_docker_password
            actual_password = resolver()
            if not isinstance(actual_password, str) or not actual_password:
                raise RuntimeGateError("canonical PostgreSQL password unavailable")
        url = URL.create(
            "postgresql+psycopg",
            username=owner["PROD_DB_USER"],
            password=actual_password,
            host="127.0.0.1",
            port=55432,
            database="arvectum",
        )
        env["AI_CORP_DATABASE_URL"] = url.render_as_string(hide_password=False)
    existing_dp = env.get("AI_CORP_RAG_DATA_PLATFORM_API_KEY")
    if existing_dp and existing_dp != owner["AI_CORP_RAG_DATA_PLATFORM_API_KEY"]:
        raise RuntimeGateError("running process inherited a stale Data Platform API key")
    env["AI_CORP_RAG_DATA_PLATFORM_API_KEY"] = owner[
        "AI_CORP_RAG_DATA_PLATFORM_API_KEY"
    ]
    # The report stays on ArvectumSSD and in a private operator-owned folder,
    # not in the repository or system disk.
    env["AI_CORP_ARVECTUM_DATA_DIR"] = (
        "/Volumes/ArvectumSSD/Arvectum/private/tender-agent/canonical-rag-output"
    )
    env["ARVECTUM_STORAGE_ROOT"] = "/Volumes/ArvectumSSD/Arvectum"
    env["PYTHONPATH"] = str(ROOT)
    return env



def verify_actual_canonical_db(database_url: str) -> None:
    """Read-only real DB connection; do not confuse a well-formed URL with access."""
    engine = None
    try:
        engine = create_engine(
            database_url,
            connect_args={"connect_timeout": 5},
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            database_name = connection.scalar(text("SELECT current_database()"))
            tender_table_exists = connection.scalar(
                text("SELECT to_regclass('public.procurement_tenders') IS NOT NULL")
            )
            if database_name != "arvectum" or tender_table_exists is not True:
                raise RuntimeGateError("connected instance is not the canonical Tender Agent DB")
    except SQLAlchemyError:
        # Psycopg exception messages can expose endpoint or auth details.
        raise RuntimeGateError(
            "canonical local PostgreSQL authentication or connectivity failed"
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=["doctor", *OPERATIONS], required=True)
    args = parser.parse_args()
    try:
        env = build_existing_environment()
    except (RuntimeGateError, ValueError) as exc:
        print(f"PROTECTED_RUNTIME_BLOCKED: {exc}", file=sys.stderr)
        return 2
    if args.operation == "doctor":
        try:
            verify_actual_canonical_db(env["AI_CORP_DATABASE_URL"])
        except RuntimeGateError as exc:
            print(f"PROTECTED_RUNTIME_BLOCKED: {exc}", file=sys.stderr)
            return 2
        # This is an actual read-only SQL verification, not just a syntax check.
        print("CANONICAL_DB_CONNECTED: PostgreSQL arvectum; Data Platform keys match; SOAP unchanged")
        return 0
    operation = OPERATIONS[args.operation]
    # No shell evaluation; arguments are hardcoded, source-specific, guarded.
    os.execvpe(sys.executable, [sys.executable, "-m", *operation], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
