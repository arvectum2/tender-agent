#!/usr/bin/env python3
"""Read-only proof that Tender Agent service and GitHub source converge on SSD."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import plistlib
import re
import shlex
import subprocess
import sys
import urllib.request

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
    checks["release_matches_github_main"] = code == 0 and github == commit
    checks["private_config"] = RELEASE_CONFIG.is_file() and RELEASE_CONFIG.stat().st_mode & 0o077 == 0
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
    checks["process_uses_release_venv"] = code == 0 and args == [
        str(venv / "bin/python"), "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8001",
    ]
    checks["workspace_not_admitted_in_marker"] = active.get("workspace_admitted") is False
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
