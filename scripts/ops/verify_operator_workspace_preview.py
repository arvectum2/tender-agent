"""Verify private APR-03B Docker runtime byte-for-byte against its source tree.

Fails closed before release/owner browser tests when any Python or UI asset in
the live container differs from the checked-out source. No environment/secrets
are read or printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path("src/modules/tender_operator_agent_demo")
IGNORED = {"__pycache__", ".DS_Store"}


def source_manifest(root: Path) -> dict[str, str]:
    package_dir = root / PACKAGE
    if not package_dir.is_dir():
        raise RuntimeError(f"Missing operator source: {package_dir}")
    return {
        str(path.relative_to(package_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package_dir.rglob("*"))
        if path.is_file()
        and not any(part in IGNORED for part in path.relative_to(package_dir).parts)
        and path.suffix != ".pyc"
    }


def manifest_differences(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    return sorted(key for key in expected.keys() | actual.keys() if expected.get(key) != actual.get(key))


_RUNTIME_CODE = """
import hashlib, json
from pathlib import Path
base = Path('/app/src/modules/tender_operator_agent_demo')
ignored = {'__pycache__', '.DS_Store'}
files = {
    str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(base.rglob('*'))
    if p.is_file() and not any(part in ignored for part in p.relative_to(base).parts)
    and p.suffix != '.pyc'
}
print(json.dumps(files, sort_keys=True))
"""


def verify_runtime(*, repo: Path, container: str, expected_commit: str) -> None:
    expected = source_manifest(repo)
    response = subprocess.run(
        ["docker", "exec", container, "python", "-c", _RUNTIME_CODE],
        capture_output=True, text=True, check=True, timeout=30,
    )
    actual = json.loads(response.stdout)
    if not isinstance(actual, dict):
        raise TypeError("Invalid Docker source manifest")
    mismatch = manifest_differences(expected, actual)
    if mismatch:
        raise RuntimeError("Operator Docker source drift: " + ", ".join(mismatch[:25]))
    label = subprocess.run(
        ["docker", "inspect", container,
         "--format", "{{index .Config.Labels \"org.opencontainers.image.revision\"}}"],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()
    if label != expected_commit:
        raise RuntimeError("Operator source commit mismatch: " + label)
    print(f"OPERATOR_IMAGE_PARITY_PASS: {len(expected)} files; commit {expected_commit[:12]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--container", default="arvectum-apr03b-preview-api")
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    verify_runtime(repo=args.repo.resolve(), container=args.container, expected_commit=args.commit)


if __name__ == "__main__":
    main()
