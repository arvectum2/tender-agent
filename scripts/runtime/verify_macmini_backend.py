#!/usr/bin/env python3
"""Read-only proof that Tender Agent service and GitHub source converge on SSD."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import plistlib
import re
import shlex
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

ROOT = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/repos/tender-agent")
RELEASES = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/releases")
RELEASE_CONFIG = pathlib.Path("/Users/master/Library/Application Support/Arvectum/tender-agent/runtime.env")
RELEASE_LAUNCHER = "/Users/master/arvectum-ops/arv-075/scripts/tender-agent-backend-ssd.sh"
LOCK = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/deploy.lock")
CONFIG = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent/runtime/backend.env")
RUNTIME = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/backend-active.json")
PLIST = pathlib.Path("/Users/master/Library/LaunchAgents/com.arvectum.backend.plist")
LAUNCHER = "/Users/master/.local/bin/tender-agent-backend-node.cjs"

def run(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 99, ""

ADMISSION = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent/wsf07b-live-admission")
REFERENCE_URL = "http://127.0.0.1:8001/api/internal/workspace/procurement-reference"


def private_json(path):
    if path.resolve() != path or path.is_symlink():
        raise ValueError("Unsafe receipt path")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
            raise ValueError("Unsafe receipt")
        raw = f.read(32769)
    if len(raw) > 32768:
        raise ValueError("Receipt too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("Invalid receipt")
    return data, hashlib.sha256(raw).hexdigest()


def anonymous_reference_status():
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(REFERENCE_URL, timeout=4) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (OSError, ValueError):
        return None


def workspace_state_matches(active, commit):
    """Verify old owner grant and exact owner-approved immutable release rebind.

    The old activation evidence is retained. A new manifest only attests to the
    original 12 IDs under a new SHA, never grants extra access or credentials.
    This read-only check does not use bearer credentials or attest fresh EIS docs.
    """
    try:
        launcher = pathlib.Path(RELEASE_LAUNCHER).read_text()
        exports = {}
        for line in launcher.splitlines():
            match = re.fullmatch(r'export (ARVECTUM_WORKSPACE_PROCUREMENT_[A-Z0-9_]+)="([^"]*)"', line)
            if match:
                if match[1] in exports:
                    return False
                exports[match[1]] = match[2]
        mode = active.get("workspace_admitted")
        if mode is False:
            return not exports and anonymous_reference_status() == 503
        if mode is not True or anonymous_reference_status() != 403:
            return False
        old_path = ADMISSION / "source-access.json"
        owner, _ = private_json(ADMISSION / "owner-admission.json")
        activation, _ = private_json(ADMISSION / "activation-evidence.json")
        expected_path = ADMISSION / f"source-access-{commit}.json"
        path = expected_path if expected_path.exists() else old_path
        manifest, pin = private_json(path)
        prefix = "ARVECTUM_WORKSPACE_PROCUREMENT_"
        if exports != {prefix + "MANIFEST": str(path),
                       prefix + "MANIFEST_SHA256": pin,
                       prefix + "SOURCE_RELEASE": "$SHA"}:
            return False
        if manifest["source_release"] != commit:
            return False
        owner_release = owner["source_release"]
        if commit == owner_release:
            if path != old_path or activation["source_manifest_sha256"] != pin:
                return False
        else:
            if path == old_path:
                return False
            original, oldpin = private_json(old_path)
            rebind, _ = private_json(ADMISSION / f"release-rebind-{commit}.json")
            if (original["source_release"] != owner_release
                or any(manifest[k] != original[k] for k in original if k != "source_release")
                or set(manifest) != set(original)
                or activation["source_manifest_sha256"] != oldpin
                or rebind["schema"] != "arvectum.wsf07b.release-rebind-local-evidence/1"
                or rebind["not_external_signature"] is not True
                or rebind["source_release_previous"] != owner_release
                or rebind["source_release_target"] != commit
                or rebind["source_manifest_sha256"] != pin
                or rebind["source_identity_count"] != 12
                or rebind["excluded_count"] != 9
                or not all(rebind[k] is True for k in (
                    "unchanged_database_binding", "unchanged_token_hash", "unchanged_validity_interval"))
                or rebind["unchanged_source_id_set_sha256"] != hashlib.sha256(
                    json.dumps(sorted(manifest["deal_ids"]), separators=(",", ":")).encode()
                ).hexdigest()):
                return False
        ids = manifest["deal_ids"]
        approved = owner["deal_ids"]
        start, end = (datetime.fromisoformat(manifest[k]) for k in ("starts_at", "expires_at"))
        if (start.utcoffset() != UTC.utcoffset(start)
            or end.utcoffset() != UTC.utcoffset(end)
            or not start <= datetime.now(UTC) < end <= datetime.fromisoformat(
                "2026-12-17T09:35:36.060836+00:00")):
            return False
        return (
            manifest["schema"] == "arvectum.tender.internal-procurement-access/1"
            and manifest["draft_blob"] == "9c0f7caa552613ab598d9de05b819524a74e8c73"
            and owner["schema"] == "arvectum.company.wsf07b.owner-admission-decision/1"
            and owner["organization"] == "organization/arvectum-company"
            and owner["source_product"] == "Tender Agent / Procurement Portfolio"
            and owner["status"] == "approved-exact-set-pending-product-and-workspace-activation"
            and activation["status"] == "source-and-workspace-read-verified"
            and activation["source_release"] == owner_release
            and activation["owner_approval_reference"] == owner["owner_approval_reference"]
            and bool(owner["owner_approval_reference"])
            and owner["database_binding"] == manifest["database_binding"]
            and owner["binding_id"] == manifest["binding_id"]
            and owner["draft_blob"] == manifest["draft_blob"]
            and owner["expires_at"] == manifest["expires_at"] == activation["expiry"]
            and isinstance(ids, list) and isinstance(approved, list)
            and len(ids) == len(set(ids)) == len(approved) == activation["admitted_count"] == 12
            and set(ids) == set(approved)
            and all(isinstance(x, str) and re.fullmatch(r"DL-[A-Za-z0-9-]{1,60}", x) for x in ids)
            and owner["excluded_count"] == activation["excluded_count"] == 9
        )
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def release_code_parity(source, commit, main_sha):
    """Allow bounded docs-only main commits, NEVER silently accept code drift.

    Uses GitHub's current compare, not mutable developer worktrees. If the
    compare cannot be proved, fail closed rather than trusting a stale local
    main checkout or converting all GitHub ancestors to accepted releases.
    """
    if main_sha == commit:
        return True
    if not re.fullmatch(r"[0-9a-f]{40}", main_sha):
        return False
    code, raw = run("gh", "api",
        f"repos/arvectum2/tender-agent/compare/{commit}...{main_sha}",
        "--jq", "{ahead_by:.ahead_by,behind_by:.behind_by,files:[.files[].filename]}")
    if code:
        return False
    try:
        proof = json.loads(raw)
        files = proof["files"]
        return (proof["behind_by"] == 0 and 1 <= proof["ahead_by"] <= 50
                and isinstance(files, list) and 1 <= len(files) <= 100
                and all(isinstance(f, str) and f.startswith((".agent/", "docs/", "specs/"))
                        for f in files))
    except (ValueError, KeyError, TypeError):
        return False


def expected_release_revision(source: pathlib.Path) -> str:
    """Require the migration head associated with this exact release source.

    Keep historical releases verifiable during rollback. Never claim a new
    database revision merely because an unmerged developer tree contains it.
    """
    migration = source / "migrations/versions/128_add_tender_async_index_receipts.py"
    return (
        "128_add_tender_async_index_receipts"
        if migration.is_file()
        else "127_private_review_link_corrections"
    )


def process_uses_release_venv(args: list[str], pid: str, venv: pathlib.Path) -> bool:
    """Verify real interpreter and loaded extension from this exact venv.

    macOS framework Python 3.15 rewrites ps argv[0] to Python.app even when
    launchd execs venv/bin/python. Checking argv[0] alone is a false negative.
    Preserve the legacy direct path test; require OS-level lsof evidence for
    framework Python rather than accepting an interpreter name by itself.
    """
    expected_tail = ["-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8001"]
    if len(args) != 1 + len(expected_tail) or args[1:] != expected_tail:
        return False
    if args[0] == str(venv / "bin/python"):
        return True
    binary = (venv / "bin/python").resolve()
    app = binary.parent.parent / "Resources/Python.app/Contents/MacOS/Python"
    if not app.is_file() or args[0] != str(app):
        return False
    proofs = tuple((venv / "lib").glob("python*/site-packages/pydantic_core/_pydantic_core*.so"))
    if len(proofs) != 1:
        return False
    code, files = run("lsof", "-nP", "-p", pid)
    if code != 0:
        return False
    return str(proofs[0]) in {line.rsplit(None, 1)[-1] for line in files.splitlines() if line.strip()}


def check_release(active: dict) -> dict:
    """Check immutable release rather than a mutable developer checkout."""
    checks: dict[str, bool] = {}
    commit = active.get("commit")
    valid_sha = isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit)
    result = {"checks": checks, "expected_repo": str(RELEASES), "active_backend_sha": None,
              "github_main_sha": None, "local_main_sha": None}
    if not valid_sha:
        checks["valid_release_sha"] = False
        return {**result, "status": "DRIFT_OR_DEGRADED"}
    result["active_backend_sha"] = commit[:12]
    release = RELEASES / ("tender-agent-" + commit)
    source = release / "source"
    venv = release / "venv"
    checks["expected_release_source"] = (
        active.get("source") == str(source) and active.get("venv") == str(venv)
        and source.is_dir() and source.resolve() == source and venv.is_dir()
        and venv.resolve() == venv
    )
    if not checks["expected_release_source"]:
        return {**result, "status": "DRIFT_OR_DEGRADED"}
    code, head = run("git", "-C", str(source), "rev-parse", "HEAD")
    checks["release_head_matches_marker"] = code == 0 and head == commit
    result["local_main_sha"] = head[:12] if code == 0 else None
    code, dirty = run("git", "-C", str(source), "status", "--porcelain", "--untracked-files=all")
    checks["release_tree_clean"] = code == 0 and not dirty
    code, github = run("gh", "api", "repos/arvectum2/tender-agent/commits/main", "--jq", ".sha")
    result["github_main_sha"] = github[:12] if code == 0 else None
    checks["release_code_parity_with_github_main"] = code == 0 and release_code_parity(source, commit, github)
    checks["private_config"] = RELEASE_CONFIG.is_file() and RELEASE_CONFIG.stat().st_mode & 0o077 == 0
    try:
        backend_launcher = pathlib.Path(RELEASE_LAUNCHER).read_text()
        daily_launcher = pathlib.Path("/Users/master/arvectum-ops/arv-075/scripts/daily-tender-ssd.sh").read_text()
        checks["backend_and_daily_release_pins"] = (
            re.findall(r"(?m)^SHA=([a-f0-9]{40})$", backend_launcher) == [commit]
            and re.findall(r'(?m)^SHA = "([a-f0-9]{40})"$', daily_launcher) == [commit]
            and f'REVISION = "{expected_release_revision(source)}"' in daily_launcher
        )
    except (OSError, ValueError):
        checks["backend_and_daily_release_pins"] = False
    try:
        plist = plistlib.loads(PLIST.read_bytes())
    except (OSError, ValueError):
        plist = {}
    checks["launch_agent_uses_release_launcher"] = plist.get("ProgramArguments") == ["/bin/bash", RELEASE_LAUNCHER]
    code, launch = run("launchctl", "print", f"gui/{os.getuid()}/com.arvectum.backend")
    checks["launch_agent_running"] = code == 0 and "state = running" in launch
    code, raw = run("lsof", "-nP", "-iTCP:8001", "-sTCP:LISTEN", "-t")
    pids = {p.strip() for p in raw.splitlines() if p.strip().isdigit()}
    checks["one_backend_listener"] = code == 0 and len(pids) == 1
    pid = next(iter(pids)) if checks["one_backend_listener"] else ""
    checks["marker_pid_matches_listener"] = bool(pid) and str(active.get("backend_pid")) == pid
    checks["launch_agent_pid_matches_listener"] = bool(pid) and bool(re.search(r"(?m)^\s*pid = " + re.escape(pid) + r"\s*$", launch))
    code, command = run("ps", "-p", pid, "-o", "command=") if pid else (1, "")
    try:
        args = shlex.split(command)
    except ValueError:
        args = []
    checks["process_uses_release_venv"] = code == 0 and process_uses_release_venv(args, pid, venv)
    checks["workspace_admission_receipt_and_anonymous_denial"] = workspace_state_matches(active, commit)
    checks["maintenance_lock_released"] = not LOCK.exists()
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:8001/health", timeout=4) as r:
            checks["http_health_200"] = r.status == 200
    except (OSError, ValueError):
        checks["http_health_200"] = False
    return {**result, "status": "OK" if all(checks.values()) else "DRIFT_OR_DEGRADED"}


def check() -> dict:
    try:
        marker = json.loads(RUNTIME.read_text())
    except (OSError, json.JSONDecodeError):
        marker = {}
    if isinstance(marker, dict) and ("venv" in marker or str(marker.get("source", "")).startswith(str(RELEASES) + "/")):
        return check_release(marker)
    result: dict = {"checks": {}, "expected_repo": str(ROOT)}
    checks = result["checks"]
    def record(label: str, good: bool):
        checks[label] = bool(good)
    record("canonical_repository_exists", ROOT.is_dir())
    _, branch = run("git", "-C", str(ROOT), "branch", "--show-current")
    _, head = run("git", "-C", str(ROOT), "rev-parse", "HEAD")
    _, remote = run("git", "-C", str(ROOT), "rev-parse", "origin/main")
    status_code, dirty = run("git", "-C", str(ROOT), "status", "--porcelain")
    result["local_main_sha"] = head[:12]
    record("canonical_main_branch", branch == "main")
    record("local_main_clean", status_code == 0 and dirty == "")
    record("local_main_tracks_origin_main", bool(head) and head == remote)
    _, github = run("gh", "api", "repos/arvectum2/tender-agent/commits/main", "--jq", ".sha")
    result["github_main_sha"] = github[:12] if github else None
    record("local_matches_github_main", bool(github) and github == head)
    record("private_runtime_config_mode_0600", CONFIG.is_file() and CONFIG.stat().st_mode & 0o077 == 0)
    try:
        plist = plistlib.loads(PLIST.read_bytes())
    except (OSError, ValueError):
        plist = {}
    record("launch_agent_uses_verified_node_wrapper",
           plist.get("ProgramArguments") == ["/opt/homebrew/bin/node", LAUNCHER])
    code, launch = run("launchctl", "print", "gui/501/com.arvectum.backend")
    record("launch_agent_running", code == 0 and "state = running" in launch)
    code, pids = run("lsof", "-nP", "-iTCP:8001", "-sTCP:LISTEN", "-t")
    pids = [p.strip() for p in pids.splitlines() if p.strip().isdigit()]
    record("one_backend_listener", code == 0 and len(pids) == 1)
    active_pid = pids[0] if len(pids) == 1 else ""
    _, process_cwd = run("lsof", "-a", "-p", active_pid, "-d", "cwd", "-Fn") if active_pid else (1, "")
    record("backend_process_cwd_is_ssd", "n" + str(ROOT) in process_cwd.splitlines())
    try:
        active = json.loads(RUNTIME.read_text())
    except (OSError, json.JSONDecodeError):
        active = {}
    result["active_backend_sha"] = str(active.get("commit", ""))[:12] or None
    record("active_backend_commit_matches_main", bool(head) and active.get("commit") == head)
    record("marker_pid_matches_listener", bool(active_pid) and str(active.get("backend_pid")) == active_pid)
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:8001/health", timeout=4) as r:
            record("http_health_200", r.status == 200)
    except (OSError, ValueError):
        record("http_health_200", False)
    result["status"] = "OK" if all(checks.values()) else "DRIFT_OR_DEGRADED"
    return result

if __name__ == "__main__":
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument("--json", action="store_true", help="machine-readable only")
    args = argp.parse_args()
    answer = check()
    if args.json:
        print(json.dumps(answer, ensure_ascii=False, indent=2))
    else:
        print(answer["status"])
        for name, passed in answer["checks"].items():
            print(("PASS" if passed else "FAIL"), name)
        print("GitHub", answer["github_main_sha"], "disk", answer["local_main_sha"], "active", answer["active_backend_sha"])
    sys.exit(0 if answer["status"] == "OK" else 1)
