"""Bounded loopback-only DP GET+SDK proof; does not authorize runtime release."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import tempfile
import time
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx
from arvectum_data_client import DataPlatformError, DataPlatformHttpClient

ALLOWED_BASE = "http://127.0.0.1:8094"
SECRET_FIELD = "ARVECTUM_DATA_INTERNAL_API_KEY"
SDK_EXPECTED = "0.4.0"


class ProbeBlocked(ValueError):
    """Sanitized failure with no request body, secret, or collection identity."""


def load_local_key(env_file: Path) -> str:
    if (not env_file.is_absolute() or env_file.is_symlink()
            or not env_file.is_file() or env_file.resolve() != env_file
            or (env_file.stat().st_mode & 0o777) != 0o600
            or not 0 < env_file.stat().st_size <= 200_000):
        raise ProbeBlocked("unsafe_private_credential_file")
    found = []
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            rf"(?:export\s+)?{SECRET_FIELD}\s*=\s*(.*)", line,
        )
        if match:
            try:
                parts = shlex.split(match.group(1), comments=False, posix=True)
            except ValueError as exc:
                raise ProbeBlocked("invalid_credential_format") from exc
            if len(parts) != 1 or not parts[0] or "\n" in parts[0]:
                raise ProbeBlocked("invalid_credential_format")
            found.append(parts[0])
    if len(found) != 1:
        raise ProbeBlocked("missing_or_ambiguous_credential")
    return found[0]


def validate_base(base: str) -> None:
    if base != ALLOWED_BASE:
        raise ProbeBlocked("non_loopback_or_wrong_data_platform_port")


def probe_once(base: str, key: str) -> dict:
    validate_base(base)
    if not key:
        raise ProbeBlocked("credential_missing")
    started = time.monotonic()
    try:
        with httpx.Client(
            base_url=base, timeout=3, follow_redirects=False, trust_env=False,
            headers={"X-Arvectum-Key": key},
        ) as transport, DataPlatformHttpClient(
            base_url=base, api_key=key, timeout_seconds=3, client=transport,
        ) as client:
            health = client.health()
            contract = client.require_contract(major=1)
            collections = client.request_json("GET", "/v1/collections")
        # One actual anonymous read must be denied; body is never logged.
        anonymous = httpx.get(
            base + "/v1/collections", timeout=3, follow_redirects=False,
            trust_env=False,
        )
    except DataPlatformError as exc:
        status = getattr(exc, "status_code", None)
        raise ProbeBlocked(f"sdk_http_{status}" if isinstance(status, int)
                           else "sdk_contract_or_response_failed") from exc
    except (httpx.HTTPError, OSError, KeyError, ValueError, TypeError) as exc:
        raise ProbeBlocked("sdk_loopback_request_failed") from exc
    if (not isinstance(health, dict)
            or health.get("status") != "ok"
            or health.get("service") != "arvectum-data"):
        raise ProbeBlocked("unverified_dp_health")
    if (not isinstance(contract, dict)
            or not str(contract.get("version", "")).startswith("1.")
            or not isinstance(contract.get("capabilities"), list)):
        raise ProbeBlocked("incompatible_consumer_contract")
    if not isinstance(collections, list) or not all(
        isinstance(row, dict) for row in collections
    ):
        raise ProbeBlocked("invalid_collections_schema")
    if anonymous.status_code != 401:
        raise ProbeBlocked("anonymous_access_not_rejected")
    return {
        "http_health_ok": True,
        "consumer_contract_major": 1,
        "collections_read_count": len(collections),
        "anonymous_collections_http": 401,
        "elapsed_ms": round(1000 * (time.monotonic() - started), 2),
    }


def audit(base: str, key: str, *, samples: int = 3, interval_ms: int = 200) -> dict:
    validate_base(base)
    if not 1 <= samples <= 5 or not 0 <= interval_ms <= 500:
        raise ProbeBlocked("invalid_bounded_probe_parameters")
    try:
        installed_sdk = version("arvectum-data-client")
    except PackageNotFoundError as exc:
        raise ProbeBlocked("sdk_distribution_unavailable") from exc
    if installed_sdk != SDK_EXPECTED:
        raise ProbeBlocked("sdk_consumer_version_mismatch")
    observations = []
    for index in range(samples):
        if index:
            time.sleep(interval_ms / 1000)
        observations.append(probe_once(base, key))
    counts = {x["collections_read_count"] for x in observations}
    if len(counts) != 1:
        raise ProbeBlocked("collection_count_changed_within_short_probe")
    return {
        "status": "PASS_BOUNDED_LOCAL_DP_SDK_GET_NOT_PRODUCTION_RELEASE",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "target": "localhost_DP_8094",
        "sdk_package_version": installed_sdk,
        "samples": samples,
        "sample_elapsed_ms": [x["elapsed_ms"] for x in observations],
        "consumer_contract_major": 1,
        "collection_count": counts.pop(),
        "anonymous_collections_rejected_401": True,
        "probe_http_methods": ["GET"],
        "probe_routes": ["/health", "/v1/contract", "/v1/collections"],
        "credential_in_receipt": False,
        "collection_ids_in_receipt": False,
        "read_only_requests": True,
        "sustained_multi_hour_reliability_proven": False,
        "owner_runtime_release_approved": False,
        "production_deployed": False,
        "production_sql_writes": 0,
        "new_source_requests": 0,
    }


def private_proof_once(path: Path, payload: dict) -> None:
    if (not path.is_absolute() or path.exists() or path.is_symlink()
            or not path.parent.is_dir() or path.parent.is_symlink()):
        raise ProbeBlocked("unsafe_or_existing_private_proof")
    fd, tmp = tempfile.mkstemp(prefix=".ta-dp-sdk-get-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(payload, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, 0o600)
        os.link(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=ALLOWED_BASE)
    parser.add_argument("--trusted-env-file", required=True, type=Path)
    parser.add_argument("--samples", default=3, type=int)
    parser.add_argument("--interval-ms", default=200, type=int)
    parser.add_argument("--private-proof-output", type=Path)
    args = parser.parse_args()
    try:
        validate_base(args.base_url)
        key = load_local_key(args.trusted_env_file)
        report = audit(
            args.base_url, key,
            samples=args.samples, interval_ms=args.interval_ms,
        )
        if args.private_proof_output:
            private_proof_once(args.private_proof_output, report)
    except ProbeBlocked as exc:
        print(json.dumps({"status": "BLOCKED_DP_READONLY_PROBE", "reason": str(exc)}))
        return 2
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        print(json.dumps({"status": "BLOCKED_DP_READONLY_PROBE", "reason": "unexpected_probe_failure"}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
