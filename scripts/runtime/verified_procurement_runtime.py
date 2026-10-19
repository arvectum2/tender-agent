"""Safely run existing source pipeline using owner-local, already provisioned files.

No passwords or API keys are printed, copied to new config files, stored in
Git, or passed in argv. These values only exist in the child process env.
The runner refuses SQLite / noncanonical databases and mismatched app keys.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
TENDER_ENV = HOME / ".config/arvectum/apr04-local.env"
PLATFORM_ENV = HOME / "Library/Application Support/Arvectum/data-platform/runtime.env"

OPERATIONS = {
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


def build_existing_environment(
    *, owner_config: Path = TENDER_ENV, platform_config: Path = PLATFORM_ENV,
    inherited: dict[str, str] | None = None, owner_uid: int | None = None,
) -> dict[str, str]:
    """Compose a restricted in-memory environment, no network or mutation."""
    uid = os.getuid() if owner_uid is None else owner_uid
    owner = _secure_env_file(owner_config, uid)
    platform = _secure_env_file(platform_config, uid)
    if owner.get("AI_CORP_RAG_DATA_PLATFORM_API_KEY") != platform.get(
        "ARVECTUM_DATA_INTERNAL_API_KEY"
    ):
        raise RuntimeGateError("Tender Agent and Data Platform keys do not match")
    if owner.get("PROD_DB_NAME") != "arvectum" or not all(
        owner.get(k) for k in ("PROD_DB_USER", "PROD_DB_PASSWORD")
    ):
        raise RuntimeGateError("existing canonical PostgreSQL settings missing")
    env = dict(os.environ if inherited is None else inherited)
    existing_dsn = env.get("AI_CORP_DATABASE_URL")
    if existing_dsn:
        parsed = make_url(existing_dsn)
        if (
            parsed.database != "arvectum" or not parsed.drivername.startswith("postgresql")
            or parsed.host not in {"127.0.0.1", "localhost"}
        ):
            raise RuntimeGateError("cannot override foreign or nonlocal database settings")
    else:
        url = URL.create(
            "postgresql+psycopg",
            username=owner["PROD_DB_USER"],
            password=owner["PROD_DB_PASSWORD"],
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
        # No secret value, hash or DSN is returned.
        print("CANONICAL_CONFIG_READY: PostgreSQL arvectum, local Data Platform, unchanged SOAP")
        return 0
    operation = OPERATIONS[args.operation]
    # No shell evaluation; arguments are hardcoded, source-specific, guarded.
    os.execvpe(sys.executable, [sys.executable, "-m", *operation], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
