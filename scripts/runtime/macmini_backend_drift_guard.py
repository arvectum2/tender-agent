#!/usr/bin/env python3
"""Read-only periodic release identity check; never restart production."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REPORT = pathlib.Path("/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/backend-drift.json")
VERIFIER = pathlib.Path.home() / ".local/bin/tender-agent-backend-verify.py"


def read_result(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def main():
    prev = read_result(REPORT)
    try:
        proc = subprocess.run(
            [sys.executable, str(VERIFIER), "--json"], capture_output=True,
            text=True, timeout=90, check=False,
        )
        result = json.loads(proc.stdout)
        if not isinstance(result, dict) or (proc.returncode and result.get("status") == "OK"):
            raise ValueError("invalid verifier output")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result = {"status": "VERIFICATION_UNAVAILABLE", "checks": {}}
    result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    REPORT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".backend-drift-", dir=REPORT.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, REPORT)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)
    if result.get("status") != "OK" and prev.get("status") == "OK":
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e",
                 'display notification "GitHub, SSD и запущенный backend расходятся. Проверьте Tender Agent." with title "Арвектум: backend drift"'],
                timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    print("Tender Agent backend drift guard:", result.get("status"),
          "github", result.get("github_main_sha"), "disk", result.get("local_main_sha"),
          "active", result.get("active_backend_sha"))
    return 0 if result.get("status") == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
