"""Verify exact post-base WAL recovery for both databases, in isolated Docker.

Default: immutable receipt preflight ONLY. --execute-isolated requires a
specific operator decision; source backup/WAL mounts stay read-only, network
disabled. A successful exact point NEVER proves seven-day retention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

IDENT = "7692004809331994662"
SCHEMA = "127_private_review_link_corrections"
WAL_BYTES = 16 * 1024 * 1024

class EvidenceError(ValueError):
    pass

def load_receipt(path: Path) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 65536:
        raise EvidenceError("receipt_missing_or_unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, OSError, UnicodeError) as exc:
        raise EvidenceError("receipt_unreadable") from exc
    if not isinstance(value, dict):
        raise EvidenceError("receipt_not_object")
    return value

def preflight(base_receipt: Path, target_receipt: Path) -> dict:
    base_data, target = load_receipt(base_receipt), load_receipt(target_receipt)
    path = base_data.get("base_path")
    if not isinstance(path, str) or not isinstance(target.get("base"), str):
        raise EvidenceError("base_path_missing")
    base = Path(path)
    if (not base.is_absolute() or base.is_symlink() or base.parent.is_symlink()
        or base.parent != base_receipt.parent or base.name != "data"
        or not base.is_dir() or str(base) != target["base"]):
        raise EvidenceError("base_identity_mismatch")
    manifest, pg = base/"backup_manifest", base/"PG_VERSION"
    if (manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 10_000_000
        or pg.is_symlink() or not pg.is_file() or pg.read_text().strip() != "17"):
        raise EvidenceError("backup_metadata_invalid")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    point = target.get("restore_point")
    if not isinstance(point, str) or not re.fullmatch(r"arvectum_pitr_check_[0-9]{8}T[0-9]{12}Z", point):
        raise EvidenceError("unbound_restore_point")
    image = base_data.get("image")
    if (base_data.get("status") != "pass" or base_data.get("live_database_mutated") is not False
        or base_data.get("source_system_identifier") != IDENT
        or target.get("status") != "pass" or target.get("business_data_mutated") is not False
        or target.get("base_manifest_sha256") != digest
        or target.get("exact_target_observed_in_server_log") is not True
        or target.get("base_end_lsn") != "6/7B288058"
        or target.get("restore_lsn") != "6/7E000090"
        or not isinstance(image, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", image)):
        raise EvidenceError("source_or_wal_receipt_mismatch")
    names = target.get("contiguous_wal")
    if (not isinstance(names, list) or not 2 <= len(names) <= 8
        or names != ["0000000100000006000000" + f"{i:02X}" for i in range(0x7B, 0x7B + len(names))]):
        raise EvidenceError("wal_segments_not_contiguous")
    wal = base.parent.parent/("wal-"+IDENT)
    if wal.is_symlink() or not wal.is_dir() or wal.parent != base.parent.parent:
        raise EvidenceError("wal_directory_invalid")
    for name in names:
        f = wal/name
        if f.is_symlink() or not f.is_file() or f.stat().st_size != WAL_BYTES:
            raise EvidenceError("wal_missing_or_bad_length")
    return {"base":base,"wal":wal,"image":image,"point":point,"manifest_sha256":digest,"wal_count":len(names)}

# All mutable data stays inside disposable container storage. Two source mounts
# are read-only, there is no network and no host PostgreSQL socket access.
ISOLATED_SH = r'''set -eu
mkdir -m 700 /tmp/restore
cp -a /backup/. /tmp/restore/
chown -R postgres:postgres /tmp/restore
chmod 700 /tmp/restore
printf "\nrestore_command='cp /wal/%%f %%p'\nrecovery_target_name='%s'\nrecovery_target_action='promote'\nrecovery_target_timeline='current'\n" "$1" >> /tmp/restore/postgresql.auto.conf
touch /tmp/restore/recovery.signal
chown postgres:postgres /tmp/restore/postgresql.auto.conf /tmp/restore/recovery.signal
gosu postgres pg_ctl -D /tmp/restore -l /tmp/restore.log -o "-c listen_addresses='' -c unix_socket_directories=/tmp -c archive_mode=off -c synchronous_standby_names=''" -w start >/dev/null
trap 'gosu postgres pg_ctl -D /tmp/restore -m fast -w stop >/dev/null || true' EXIT
for i in $(seq 1 60); do
 if test "$(psql -XqAt -h /tmp -U arvectum -d arvectum_data -c 'SELECT pg_is_in_recovery()' 2>/dev/null || true)" = f; then break; fi
 sleep 1
done
grep -F "recovery stopping at restore point \"$1\"" /tmp/restore.log >/dev/null
echo EXACT_RESTORE_POINT_OBSERVED_IN_PG_LOG
psql -XqAt -h /tmp -U arvectum -d arvectum -v ON_ERROR_STOP=1 -c "SELECT json_build_object('database',current_database(),'recovery',pg_is_in_recovery(),'system_identifier',(SELECT system_identifier::text FROM pg_control_system()),'revision',(SELECT version_num FROM alembic_version),'tenders',(SELECT count(*) FROM procurement_tenders),'new_tables',(SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename IN ('application_review_previews','application_review_decisions','original_form_review_candidates','original_form_review_receipts','private_review_retention_proposals','private_review_order_links','private_review_link_corrections')))"
psql -XqAt -h /tmp -U arvectum -d arvectum_data -v ON_ERROR_STOP=1 -c "SELECT json_build_object('database',current_database(),'recovery',pg_is_in_recovery(),'system_identifier',(SELECT system_identifier::text FROM pg_control_system()),'collections',(SELECT count(*) FROM dp_collections))"
'''

def verify_rows(output: str) -> dict:
    if "EXACT_RESTORE_POINT_OBSERVED_IN_PG_LOG" not in output.splitlines():
        raise EvidenceError("no_exact_target_in_server_log")
    rows = {}
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("database") in {"arvectum", "arvectum_data"}:
            if item["database"] in rows:
                raise EvidenceError("duplicate_restored_database")
            rows[item["database"]] = item
    if set(rows) != {"arvectum", "arvectum_data"}:
        raise EvidenceError("missing_restored_database")
    biz, dp = rows["arvectum"], rows["arvectum_data"]
    if (any(r.get("system_identifier") != IDENT or r.get("recovery") is not False for r in rows.values())
        or biz.get("revision") != SCHEMA or not isinstance(biz.get("tenders"), int)
        or biz["tenders"] < 64 or biz.get("new_tables") != 7
        or not isinstance(dp.get("collections"), int) or dp["collections"] < 73):
        raise EvidenceError("restored_database_or_schema_invalid")
    return {"business_revision":biz["revision"],"business_tenders":biz["tenders"],"dp_collections":dp["collections"]}

def run_isolated(state: dict) -> dict:
    cmd = [
        "/opt/homebrew/bin/docker", "run", "--rm", "--pull", "never",
        "--network", "none", "--pids-limit", "256", "--entrypoint", "/bin/sh",
        "--mount", f"type=bind,src={state['base']},dst=/backup,readonly",
        "--mount", f"type=bind,src={state['wal']},dst=/wal,readonly",
        state["image"], "-c", ISOLATED_SH, "restore", state["point"],
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=420)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("isolated_restore_unavailable") from exc
    if proc.returncode:
        raise EvidenceError("isolated_restore_failed")
    return verify_rows(proc.stdout)

def save_once(path: Path, data: dict):
    if (not path.is_absolute() or path.parent.is_symlink()
        or not path.parent.is_dir() or path.is_symlink()):
        raise EvidenceError("receipt_destination_untrusted")
    if path.exists():
        raise EvidenceError("receipt_already_exists")
    fd, temporary = tempfile.mkstemp(prefix=".pitr-proof-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(data, file, ensure_ascii=False, sort_keys=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o600)
        os.link(temporary, path)
    except (OSError, ValueError) as exc:
        raise EvidenceError("receipt_write_failed") from exc
    finally:
        Path(temporary).unlink(missing_ok=True)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-receipt", required=True, type=Path)
    parser.add_argument("--target-receipt", required=True, type=Path)
    parser.add_argument("--execute-isolated", action="store_true")
    parser.add_argument("--proof-output", type=Path)
    args = parser.parse_args()
    try:
        state = preflight(args.base_receipt, args.target_receipt)
        outcome = {
            "contract":"ta-pitr-exact-postbase-wal-dual-database-v1",
            "preflight":"PASS", "isolated_restore":"NOT_EXECUTED",
            "exact_postbase_target":"NOT_PROVEN", "continuous_seven_day_pitr":"NOT_PROVEN",
            "production_writes":0, "source_mounts":"read_only", "network":"none",
            "base_manifest_sha256":state["manifest_sha256"],
            "target_restore_point":state["point"], "wal_segment_count":state["wal_count"],
        }
        if args.execute_isolated:
            if args.proof_output is None:
                raise EvidenceError("immutable_receipt_required")
            outcome.update(run_isolated(state))
            outcome["isolated_restore"] = outcome["exact_postbase_target"] = "PASS"
            outcome["verified_at_utc"] = datetime.now(UTC).isoformat()
            save_once(args.proof_output, outcome)
        elif args.proof_output is not None:
            raise EvidenceError("dry_run_cannot_write")
    except (EvidenceError, OSError, UnicodeError) as exc:
        code = str(exc) if isinstance(exc, EvidenceError) else "preflight_unavailable"
        print(json.dumps({"status":"BLOCKED","error_code":code,"continuous_seven_day_pitr":"NOT_PROVEN"}))
        return 2
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
