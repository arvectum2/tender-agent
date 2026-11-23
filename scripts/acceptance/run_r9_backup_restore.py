"""Disposable R9 backup/restore and mismatch acceptance matrix."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "tests/integration/compose.r8-postgres.yml"
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))
sys.path.insert(0, str(ROOT / "scripts" / "ops"))
from r8_acceptance.runtime import http
from r9_recovery import (
    RecoveryError,
    create_backup,
    restore_backup,
    restore_database,
    restore_filesystem,
    verify_backup,
)
from run_r9_db_filesystem_mismatch import bootstrap, port, run, start, stop, write

CUSTOMER = "R9-RECOVERY"
STATUS = "R9_P2_BACKUP_RESTORE_FAIL_CLOSED"
FILES = (
    "backup-restore-result.json",
    "backup-manifest.json",
    "consistent-restore.json",
    "db-only-mismatch.json",
    "filesystem-only-mismatch.json",
    "cross-tenant-mismatch.json",
    "snapshots.json",
    "assertions.json",
    "cleanup.json",
    "commands.log",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def database_url(base: str, name: str) -> str:
    parsed = urlsplit(base)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{name}", parsed.query, ""))


def create_database(admin_url: str, name: str) -> None:
    if not name.replace("_", "").isalnum():
        raise RuntimeError("unsafe database name")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        engine.dispose()


def db_snapshot(url: str, state: dict[str, str] | None = None) -> dict[str, Any]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('pg_catalog','information_schema')"
                    )
                ).scalar_one()
            )
            if tables == 0:
                return {"table_count": 0, "customers": [], "binding": None, "artifact": None}
            customers = [
                str(row[0])
                for row in connection.execute(
                    text("SELECT customer_id FROM customer_profiles ORDER BY customer_id")
                )
            ]
            binding = artifact = None
            if state:
                binding_row = connection.execute(
                    text(
                        "SELECT id,run_id,requirements_file_sha256,canonical_report_file_sha256 "
                        "FROM pilot_run_results WHERE run_id=:run_id"
                    ),
                    {"run_id": state["run_id"]},
                ).mappings().first()
                artifact_row = connection.execute(
                    text(
                        "SELECT id,run_id,artifact_key,pdf_sha256,byte_size "
                        "FROM pilot_artifacts WHERE run_id=:run_id"
                    ),
                    {"run_id": state["run_id"]},
                ).mappings().first()
                binding = dict(binding_row) if binding_row else None
                artifact = dict(artifact_row) if artifact_row else None
            return {
                "table_count": tables,
                "customers": customers,
                "binding": binding,
                "artifact": artifact,
            }
    finally:
        engine.dispose()


def tree_snapshot(root: Path) -> dict[str, Any]:
    files = []
    if root.exists():
        for item in sorted(root.rglob("*")):
            if item.is_file():
                files.append(
                    {
                        "path": str(item.relative_to(root)),
                        "sha256": sha(item),
                        "size": item.stat().st_size,
                    }
                )
    return {"exists": root.exists(), "files": files}


def request(method: str, url: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        status, raw, _ = http(method, url, username="", password="", body=body, headers=headers)
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"body_present": bool(raw)}
        return {"status_code": status, "body": parsed}
    except Exception as exc:  # noqa: BLE001 - synthetic HTTP acceptance error boundary
        return {"exception_type": type(exc).__name__, "message": str(exc)[:200]}


def download(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = response.read()
            return {
                "status_code": response.status,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload),
            }
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code}


def checksums(evidence: Path) -> dict[str, Any]:
    names = sorted(path.name for path in evidence.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    (evidence / "SHA256SUMS").write_text("".join(f"{sha(evidence / name)}  {name}\n" for name in names))
    rows = [line.split("  ", 1) for line in (evidence / "SHA256SUMS").read_text().splitlines()]
    bad = [name for digest, name in rows if not (evidence / name).is_file() or sha(evidence / name) != digest]
    return {
        "valid": names == sorted(FILES) and len(rows) == len(FILES) and len({name for _, name in rows}) == len(rows) and not bad,
        "entry_count": len(rows),
        "expected_file_count": len(FILES),
        "missing_files": sorted(set(FILES) - set(names)),
        "unexpected_files": sorted(set(names) - set(FILES)),
        "hash_mismatches": bad,
    }


def main() -> int:
    evidence = ROOT / "output" / f"r9-backup-restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    evidence.mkdir(parents=True)
    temp = Path(tempfile.mkdtemp(prefix="r9-backup-restore-", dir=ROOT / "output"))
    source_data = temp / "source-data"
    source_data.mkdir()
    backups = temp / "backups"
    commands: list[dict[str, Any]] = []
    cleanup: dict[str, Any] = {"errors": []}
    started = time.monotonic()
    process = None
    password = "r9-" + secrets.token_urlsafe(12)
    dbport = port()
    compose_project = "r9br" + secrets.token_hex(4)
    source_url = f"postgresql+psycopg://r8_acceptance:{password}@127.0.0.1:{dbport}/r8_acceptance"
    original_path = os.environ.get("PATH")
    env = os.environ.copy()
    env.update(
        R8_POSTGRES_PASSWORD=password,
        R8_POSTGRES_PORT=str(dbport),
        AI_CORP_DATABASE_URL=source_url,
        AI_CORP_ARVECTUM_DATA_DIR=str(source_data),
        AI_CORP_PILOT_AUTH_ENABLED="false",
        AI_CORP_TENDER_PILOT_BASIC_AUTH_ENABLED="false",
    )
    consistent: dict[str, Any] = {}
    db_only: dict[str, Any] = {}
    fs_only: dict[str, Any] = {}
    cross: dict[str, Any] = {}
    source_snapshots: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    try:
        compose = ["docker", "compose", "-p", compose_project, "-f", str(COMPOSE)]
        run(compose + ["up", "-d", "--wait"], env, commands)
        # The disposable server is PG16. Use its native pg_dump/pg_restore
        # instead of incompatible host binaries (e.g. Homebrew PG18). Do not
        # alter the production recovery implementation or test atomicity.
        result = subprocess.run(
            compose + ["ps", "-q", "postgres"], cwd=ROOT, env=env,
            capture_output=True, text=True, check=True, timeout=12,
        )
        container_id = result.stdout.strip()
        if not container_id:
            raise RuntimeError("R9 disposable PostgreSQL container unavailable")
        owner = subprocess.run(
            ["docker", "inspect", "-f", '{{index .Config.Labels "com.docker.compose.project"}}', container_id],
            capture_output=True, text=True, check=True, timeout=12,
        ).stdout.strip()
        if owner != compose_project:
            raise RuntimeError("R9 PostgreSQL container ownership mismatch")
        native_client = subprocess.run(
            ["docker", "exec", container_id, "pg_restore", "--version"],
            capture_output=True, text=True, check=True, timeout=12,
        ).stdout.strip()
        if "PostgreSQL) 16." not in native_client:
            raise RuntimeError("R9 acceptance requires matching PostgreSQL 16 clients")
        bin_dir = temp / "pg-client-bin"
        bin_dir.mkdir(mode=0o700)
        adapter = ROOT / "scripts" / "acceptance" / "r9_pg_container_client.py"
        for program in ("pg_dump", "pg_restore"):
            target = bin_dir / program
            shutil.copyfile(adapter, target)
            target.chmod(0o700)
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{original_path or ''}"
        os.environ["R9_PG_TEST_CONTAINER"] = container_id
        os.environ["R9_PG_TEST_PORT"] = str(dbport)
        run([sys.executable, "-m", "alembic", "upgrade", "head"], env, commands)
        seed = '''import os,sys
sys.path.insert(0,"scripts/acceptance")
from run_r8_acceptance import _seed
_seed(os.environ)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.modules.customer_registry.models import CustomerProfile
with Session(create_engine(os.environ["AI_CORP_DATABASE_URL"])) as s:
 s.add(CustomerProfile(customer_id="R9-RECOVERY",legal_name="R9",customer_status="prospect"));s.commit()'''
        run([sys.executable, "-c", seed], env, commands)
        boot = temp / "boot.py"
        bootstrap(boot)
        process = start(boot, env)
        base = f"http://127.0.0.1:{process.r9_port}/api/operator/pilot/customers/{CUSTOMER}"
        project = request("POST", base + "/projects", {"name": "recovery"})
        project_id = project["body"]["id"]
        case = request("POST", base + f"/projects/{project_id}/cases", {"procurement_number": "0379100000726000101"})
        case_id = case["body"]["id"]
        run_response = request("POST", base + f"/cases/{case_id}/runs", {}, {"Idempotency-Key": "recovery"})
        run_id = run_response["body"]["id"]
        state = {"project_id": project_id, "case_id": case_id, "run_id": run_id}
        completed = request("POST", base + f"/cases/{case_id}/runs/{run_id}/complete", {})
        exported = request("POST", base + f"/cases/{case_id}/runs/{run_id}/artifacts/final-pdf", {})
        if completed.get("status_code") != 200 or exported.get("status_code") != 201:
            raise RuntimeError("source publication failed")
        source_download = download(base + f"/cases/{case_id}/runs/{run_id}/artifacts/final-pdf")
        if source_download.get("status_code") != 200:
            raise RuntimeError("source artifact download failed")
        source_snapshots = {
            "database": db_snapshot(source_url, state),
            "filesystem": tree_snapshot(source_data),
            "download": source_download,
        }
        stop(process)
        process = None

        backup_dir = create_backup(database_url=source_url, data_dir=source_data, output_dir=backups, quiesced=True)
        manifest = verify_backup(backup_dir)

        consistent_name = "r9_restore_consistent"
        create_database(source_url, consistent_name)
        consistent_url = database_url(source_url, consistent_name)
        consistent_data = temp / "consistent-data"
        receipt = restore_backup(
            database_url=consistent_url,
            data_dir=consistent_data,
            backup_dir=backup_dir,
            expected_tenants=set(manifest["tenant_scope"]),
            quiesced=True,
        )
        consistent_env = env.copy()
        consistent_env.update(AI_CORP_DATABASE_URL=consistent_url, AI_CORP_ARVECTUM_DATA_DIR=str(consistent_data))
        consistent_process = start(boot, consistent_env)
        consistent_base = f"http://127.0.0.1:{consistent_process.r9_port}/api/operator/pilot/customers/{CUSTOMER}"
        consistent_download = download(consistent_base + f"/cases/{case_id}/runs/{run_id}/artifacts/final-pdf")
        stop(consistent_process)
        consistent = {
            "receipt": receipt,
            "database": db_snapshot(consistent_url, state),
            "filesystem": tree_snapshot(consistent_data),
            "download": consistent_download,
        }
        consistent["safe"] = bool(
            consistent["database"] == source_snapshots["database"]
            and consistent["filesystem"] == source_snapshots["filesystem"]
            and consistent_download == source_download
        )

        db_only_name = "r9_restore_db_only"
        create_database(source_url, db_only_name)
        db_only_url = database_url(source_url, db_only_name)
        restore_database(database_url=db_only_url, database_dump=backup_dir / "database.dump")
        db_only_data = temp / "db-only-data"
        db_only_data.mkdir()
        db_only_env = env.copy()
        db_only_env.update(AI_CORP_DATABASE_URL=db_only_url, AI_CORP_ARVECTUM_DATA_DIR=str(db_only_data))
        db_only_process = start(boot, db_only_env)
        db_only_base = f"http://127.0.0.1:{db_only_process.r9_port}/api/operator/pilot/customers/{CUSTOMER}"
        db_only_download = download(db_only_base + f"/cases/{case_id}/runs/{run_id}/artifacts/final-pdf")
        stop(db_only_process)
        db_only = {
            "database": db_snapshot(db_only_url, state),
            "filesystem": tree_snapshot(db_only_data),
            "download": db_only_download,
        }
        db_only["safe"] = bool(
            db_only_download.get("status_code") == 409
            and db_only["database"]["artifact"] is not None
            and not db_only["filesystem"]["files"]
        )

        fs_only_name = "r9_restore_fs_only"
        create_database(source_url, fs_only_name)
        fs_only_url = database_url(source_url, fs_only_name)
        fs_env = env.copy()
        fs_env["AI_CORP_DATABASE_URL"] = fs_only_url
        run([sys.executable, "-m", "alembic", "upgrade", "head"], fs_env, commands)
        fs_only_data = temp / "fs-only-data"
        restore_filesystem(filesystem_tar=backup_dir / "filesystem.tar", data_dir=fs_only_data)
        fs_only_env = env.copy()
        fs_only_env.update(AI_CORP_DATABASE_URL=fs_only_url, AI_CORP_ARVECTUM_DATA_DIR=str(fs_only_data))
        fs_only_process = start(boot, fs_only_env)
        fs_only_base = f"http://127.0.0.1:{fs_only_process.r9_port}/api/operator/pilot/customers/{CUSTOMER}"
        fs_only_case = request("GET", fs_only_base + f"/cases/{case_id}")
        stop(fs_only_process)
        fs_only = {
            "database": db_snapshot(fs_only_url, state),
            "filesystem": tree_snapshot(fs_only_data),
            "case_request": fs_only_case,
        }
        fs_only["safe"] = bool(
            fs_only_case.get("status_code") == 404
            and fs_only["database"]["binding"] is None
            and fs_only["database"]["artifact"] is None
            and fs_only["filesystem"] == source_snapshots["filesystem"]
        )

        cross_name = "r9_restore_cross_tenant"
        create_database(source_url, cross_name)
        cross_url = database_url(source_url, cross_name)
        cross_data = temp / "cross-data"
        rejected = False
        try:
            restore_backup(
                database_url=cross_url,
                data_dir=cross_data,
                backup_dir=backup_dir,
                expected_tenants={"WRONG-TENANT"},
                quiesced=True,
            )
        except RecoveryError:
            rejected = True
        cross = {
            "rejected": rejected,
            "database": db_snapshot(cross_url),
            "filesystem": tree_snapshot(cross_data),
        }
        cross["safe"] = bool(rejected and cross["database"]["table_count"] == 0 and not cross_data.exists())
    finally:
        if process:
            try:
                stop(process)
            except Exception as exc:  # noqa: BLE001 - cleanup must always continue
                cleanup["errors"].append(type(exc).__name__)
        cleanup["compose_down_returncode"] = subprocess.run(
            ["docker", "compose", "-p", compose_project, "-f", str(COMPOSE), "down", "--volumes", "--remove-orphans"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
        ).returncode
        for name, command in {
            "containers": ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={compose_project}"],
            "networks": ["docker", "network", "ls", "-q", "--filter", f"name={compose_project}"],
            "volumes": ["docker", "volume", "ls", "-q", "--filter", f"name={compose_project}"],
        }.items():
            value = subprocess.run(command, text=True, capture_output=True, check=False)
            cleanup[f"{name}_check_returncode"] = value.returncode
            cleanup[name] = value.stdout.split()
        # Never leak temporary pg tool selection to other tests or jobs.
        if original_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = original_path
        os.environ.pop("R9_PG_TEST_CONTAINER", None)
        os.environ.pop("R9_PG_TEST_PORT", None)
        shutil.rmtree(temp, ignore_errors=True)
        cleanup["temporary_root_removed"] = not temp.exists()
        cleanup["cleanup_complete"] = not cleanup["errors"] and cleanup["compose_down_returncode"] == 0 and all(cleanup[f"{name}_check_returncode"] == 0 and not cleanup[name] for name in ("containers", "networks", "volumes")) and cleanup["temporary_root_removed"]

    assertions = {
        "backup_manifest_verified": bool(manifest),
        "consistent_restore_exact": bool(consistent.get("safe")),
        "db_only_restore_fails_closed": bool(db_only.get("safe")),
        "filesystem_only_restore_fails_closed": bool(fs_only.get("safe")),
        "cross_tenant_restore_rejected_pre_mutation": bool(cross.get("safe")),
    }
    write(evidence / "backup-manifest.json", manifest)
    write(evidence / "consistent-restore.json", consistent)
    write(evidence / "db-only-mismatch.json", db_only)
    write(evidence / "filesystem-only-mismatch.json", fs_only)
    write(evidence / "cross-tenant-mismatch.json", cross)
    write(evidence / "snapshots.json", {"source": source_snapshots, "consistent": consistent, "db_only": db_only, "filesystem_only": fs_only, "cross_tenant": cross})
    write(evidence / "assertions.json", assertions)
    write(evidence / "cleanup.json", cleanup)
    write(evidence / "commands.log", commands)
    result = {
        "status": STATUS if all(assertions.values()) else "R9_P2_BACKUP_RESTORE_UNSAFE",
        "backup_created": bool(manifest),
        "consistent_restore": bool(consistent.get("safe")),
        "db_only_mismatch_fail_closed": bool(db_only.get("safe")),
        "filesystem_only_mismatch_fail_closed": bool(fs_only.get("safe")),
        "cross_tenant_mismatch_rejected": bool(cross.get("safe")),
        "assertions": assertions,
        "cleanup": cleanup,
        "duration_seconds": time.monotonic() - started,
    }
    write(evidence / "backup-restore-result.json", result)
    serialized = "\n".join(path.read_text(errors="replace") for path in evidence.iterdir() if path.is_file())
    result["hygiene"] = {"passed": password not in serialized and str(temp) not in serialized, "hits": [] if password not in serialized and str(temp) not in serialized else ["forbidden"]}
    result["checksum_validator"] = {"valid": {path.name for path in evidence.iterdir() if path.is_file()} == set(FILES), "entry_count": len(FILES), "expected_file_count": len(FILES)}
    write(evidence / "backup-restore-result.json", result)
    checksum_details = checksums(evidence)
    print(evidence)
    return 0 if result["status"] == STATUS and cleanup["cleanup_complete"] and result["hygiene"]["passed"] and checksum_details["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
