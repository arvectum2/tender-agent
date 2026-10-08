"""APR-03 Linux production preflight and non-destructive evidence utilities.

No public deployment or destructive restore occurs here. A restore is allowed
only into a fresh, isolated arvectum-restore-* Compose project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy/production/compose.yaml"
SAFE_PROJECT = re.compile(r"^[a-z][a-z0-9-]{2,50}$")
SAFE_SECRET = re.compile(r"^[A-Za-z0-9_-]{32,}$")
SAFE_DOMAIN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
REQUIRED = ("PROD_DOMAIN", "PROD_ACME_EMAIL", "PROD_DB_USER", "PROD_DB_NAME",
            "PROD_DB_PASSWORD", "PROD_REDIS_PASSWORD",
            "AI_CORP_PILOT_AUTH_USERNAME", "AI_CORP_PILOT_AUTH_PASSWORD",
            "ZAKUPKI_GOV_RU_SOAP_TOKEN")


def run(argv: list[str], *, input_file=None, output_file=None, capture=False):
    return subprocess.run(argv, stdin=input_file, stdout=subprocess.PIPE if capture else output_file,
                          check=True, text=False)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def secure_env(path: Path) -> dict[str, str]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("secret environment file must be an existing non-symlink absolute file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("secret environment file requires exact mode 0600")
    if path.resolve().is_relative_to(ROOT):
        raise ValueError("secret environment file must be outside repository")
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("invalid environment line")
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
            raise ValueError("invalid or duplicated environment key")
        result[key] = value.strip("'\"")
    if any(not result.get(key) for key in REQUIRED):
        raise ValueError("required production environment field missing")
    if not SAFE_DOMAIN.fullmatch(result["PROD_DOMAIN"]) or result["PROD_DOMAIN"].endswith(".invalid"):
        raise ValueError("valid public DNS name required")
    if "@" not in result["PROD_ACME_EMAIL"] or result["PROD_ACME_EMAIL"].endswith(".invalid"):
        raise ValueError("real ACME contact required")
    if any(not SAFE_SECRET.fullmatch(result[k]) for k in
           ("PROD_DB_PASSWORD", "PROD_REDIS_PASSWORD", "AI_CORP_PILOT_AUTH_PASSWORD")):
        raise ValueError("each password must use 32+ URL-safe random characters")
    if len({result[k] for k in ("PROD_DB_PASSWORD", "PROD_REDIS_PASSWORD",
                              "AI_CORP_PILOT_AUTH_PASSWORD")}) != 3:
        raise ValueError("production passwords must be distinct")
    if result.get("AI_CORP_PILOT_AUTH_ENABLED", "true").lower() != "true":
        raise ValueError("operator authentication must remain enabled")
    return result


def runtime_env(args, secrets: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(secrets)
    env.update({
        "PROD_SECRET_ENV": str(args.env_file),
        "PROD_ETP_TRUST_DIR": str(args.trust_dir),
        "ARVECTUM_IMAGE_REVISION": args.revision,
        "ARVECTUM_IMAGE_VERSION": args.version,
    })
    return env


def compose(args, *command, env=None, capture=False, input_file=None, output_file=None):
    cmd = ["docker", "compose", "--project-name", args.project, "--env-file",
           str(args.env_file), "-f", str(COMPOSE), *command]
    return subprocess.run(cmd, check=True, env=env, stdin=input_file,
                          stdout=subprocess.PIPE if capture else output_file)


def common(args, *, require_clean=False):
    secrets = secure_env(args.env_file)
    if not args.trust_dir.is_absolute() or args.trust_dir.is_symlink() or not (
            args.trust_dir / "policy.yaml").is_file():
        raise ValueError("external TLS trust directory and policy.yaml required")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("exact image commit SHA required")
    current = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if current != args.revision:
        raise ValueError("checked-out commit does not match requested image revision")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,64}", args.version):
        raise ValueError("release version is invalid")
    if require_clean and subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"]).strip():
        raise ValueError("release checkout is not clean")
    if not SAFE_PROJECT.fullmatch(args.project):
        raise ValueError("invalid Compose project name")
    return runtime_env(args, secrets)


def preflight(args):
    env = common(args, require_clean=True)
    compose(args, "config", "--quiet", env=env)
    run(["docker", "info"], output_file=subprocess.DEVNULL)
    print("APR-03 preflight passed (no production mutation)")


def verify(folder: Path):
    folder = folder.resolve(strict=True)
    manifest_file = folder / "manifest.json"
    if manifest_file.is_symlink() or not manifest_file.is_file():
        raise ValueError("manifest missing or symlink")
    manifest = json.loads(manifest_file.read_text())
    if manifest.get("format") != "arvectum-apr03-backup-v1":
        raise ValueError("unsupported backup manifest version")
    if not SAFE_PROJECT.fullmatch(manifest.get("source_project", "")):
        raise ValueError("invalid backup source project")
    for name in ("database.dump", "files.tar.gz"):
        file = folder / name
        if file.is_symlink() or not file.is_file() or not file.stat().st_size:
            raise ValueError("missing backup part or symlink")
        if digest(file) != manifest["parts"][name]["sha256"]:
            raise ValueError("backup checksum mismatch")
        if file.stat().st_size != manifest["parts"][name]["bytes"]:
            raise ValueError("backup byte count mismatch")
    with (folder / "database.dump").open("rb") as dump:
        header = dump.read(5)
    if header != b"PGDMP":
        raise ValueError("not a PostgreSQL custom-format dump")
    with tarfile.open(folder / "files.tar.gz", "r:gz") as archive:
        seen = set()
        for member in archive:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or not name.parts
                or name.parts[0] not in ("data", "artifacts", "eis-archives")
                or not (member.isfile() or member.isdir()) or member.name in seen):
                raise ValueError("unsafe or duplicate file archive member")
            seen.add(member.name)
    return manifest


def backup(args):
    env = common(args)
    if not args.output.is_absolute() or args.output.exists() or args.output.resolve().is_relative_to(ROOT):
        raise ValueError("new absolute backup directory outside repository required")
    if not args.encrypted_destination_confirmed:
        raise ValueError("confirm independent encrypted backup destination explicitly")
    compose(args, "exec", "-T", "db", "sh", "-ec",
            'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"', env=env,
            output_file=subprocess.DEVNULL)
    api_id = compose(args, "ps", "-q", "api", env=env, capture=True).stdout.decode().strip()
    if not api_id:
        raise ValueError("source API is not running")
    # The destination remains unpublished until both archives and verification pass.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".apr03-incomplete-", dir=args.output.parent) as temp:
        folder = Path(temp)
        folder.chmod(0o700)
        with (folder / "database.dump").open("wb") as out:
            compose(args, "exec", "-T", "db", "sh", "-ec",
                    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges',
                    env=env, output_file=out)
        with (folder / "files.tar.gz").open("wb") as out:
            run(["docker", "run", "--rm", "--volumes-from", api_id + ":ro",
                 "alpine:3.20", "tar", "-C", "/app", "-czf", "-",
                 "data", "artifacts", "eis-archives"], output_file=out)
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        manifest = {
            "format": "arvectum-apr03-backup-v1",
            "source_project": args.project,
            "application_commit": commit,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "parts": {n: {"sha256": digest(folder / n), "bytes": (folder / n).stat().st_size}
                      for n in ("database.dump", "files.tar.gz")},
            "private_data": True,
            "encrypted_off_host_storage": "operator_asserted_not_verified",
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        verify(folder)
        folder.rename(args.output)
    print("APR-03 backup published and verified")


def restore(args):
    manifest = verify(args.backup)
    env = common(args)
    if not args.project.startswith("arvectum-restore-") or args.project == manifest["source_project"]:
        raise ValueError("restore target must be a distinct arvectum-restore-* project")
    if manifest["application_commit"] != args.revision:
        raise ValueError("restore requires the exact application commit from backup")
    # Fail before touching Docker if ANY target volume exists; never --replace.
    for name in ("db", "redis", "app-data", "app-artifacts", "app-eis"):
        probe = subprocess.run(["docker", "volume", "inspect", f"{args.project}_{name}"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if probe.returncode == 0:
            raise ValueError("restore target volumes already exist: refusing overwrite")
    compose(args, "up", "-d", "db", "redis", env=env)
    with (args.backup / "database.dump").open("rb") as source:
        compose(args, "exec", "-T", "db", "sh", "-ec",
                'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges',
                env=env, input_file=source)
    volumes = ("app-data", "app-artifacts", "app-eis")
    for name in volumes:
        run(["docker", "volume", "create", f"{args.project}_{name}"],
            output_file=subprocess.DEVNULL)
    # Archive was exhaustively path/link-validated by verify().
    run(["docker", "run", "--rm",
         "-v", f"{args.project}_app-data:/restore/data",
         "-v", f"{args.project}_app-artifacts:/restore/artifacts",
         "-v", f"{args.project}_app-eis:/restore/eis-archives",
         "-v", f"{args.backup.resolve()}:/backup:ro",
         "alpine:3.20", "tar", "-C", "/restore", "-xzf", "/backup/files.tar.gz"])
    compose(args, "up", "-d", "--build", "api", "worker", env=env)
    compose(args, "exec", "-T", "api", "python", "-c",
            "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=10).status == 200",
            env=env)
    print("APR-03 isolated restore smoke passed; no public ingress was started")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    verify_p = subs.add_parser("verify")
    verify_p.add_argument("--backup", type=Path, required=True)
    for kind in ("preflight", "backup", "restore"):
        p = subs.add_parser(kind)
        p.add_argument("--project", required=True)
        p.add_argument("--env-file", type=Path, required=True)
        p.add_argument("--trust-dir", type=Path, required=True)
        p.add_argument("--revision", required=True)
        p.add_argument("--version", required=True)
        if kind == "backup":
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--encrypted-destination-confirmed", action="store_true")
        if kind == "restore":
            p.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    try:
        {"verify": lambda: verify(args.backup),
         "preflight": lambda: preflight(args),
         "backup": lambda: backup(args),
         "restore": lambda: restore(args)}[args.action]()
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError,
            json.JSONDecodeError, tarfile.TarError) as error:
        print(f"APR-03 {args.action} FAILED: {type(error).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
