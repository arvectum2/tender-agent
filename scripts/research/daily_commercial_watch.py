"""Bounded, source-only daily commercial watch; opt-in execution, no production DB.

Dry-run is strictly offline. --execute writes private report/receipts; optional
--capture-sibur additionally performs only public first-party HTTPS GET via
the existing bounded SIBUR capture module. Never signs into supplier portals,
sends bids, touches Tender Agent databases or launches model inference.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts.research.commercial_watch import (
    EvidenceRejected,
    _time,
    compile_watch,
    render_markdown,
)

GEH_PATTERN = re.compile(r"^geh-active-refresh-\d{8}T\d{6}Z$")
RUN_PATTERN = re.compile(r"^\d{8}T\d{6}\d{6}Z$")
SPACE_MIN_BYTES = 2 * 1024**3  # public JSON pages + reports only, never a DB backup
CAPTURE_MAX_PAGES = 40


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(131072), b""):
            h.update(block)
    return h.hexdigest()


def _safe_dir(path: Path, *, create: bool) -> Path:
    # Source parent paths may be a trusted ArvectumSSD symlink; do not
    # follow attacker-added leaf symlinks or overwrite existing user files.
    if path.is_symlink():
        raise EvidenceRejected(f"unexpected symlink at leaf directory: {path.name}")
    if not path.exists() and create:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not path.is_dir() or path.is_symlink():
        raise EvidenceRejected(f"missing or unsafe private directory: {path.name}")
    if create and path.stat().st_mode & 0o077:
        raise EvidenceRejected("existing private directory has unsafe group/other access")
    return path


def latest_geh(root: Path) -> Path:
    _safe_dir(root, create=False)
    names = sorted(x for x in root.iterdir() if GEH_PATTERN.fullmatch(x.name))
    if not names:
        raise EvidenceRejected("no GEH source snapshots were found")
    newest = names[-1]
    # Never silently fall back to an older successful snapshot: the newest
    # in-progress or failed capture must remain a visible blocked result.
    _safe_dir(newest, create=False)
    if not (newest / "guarded-ingest" / "state.json").is_file():
        raise EvidenceRejected("newest GEH capture is incomplete; no fallback")
    return newest


def _atomic_private_json(path: Path, value: dict) -> None:
    """Atomic replace of only our own status pointers, never imported sources."""
    if path.is_symlink():
        raise EvidenceRejected("unexpected symlink at status destination")
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp = path.with_name(path.name + ".tmp")
    if temp.is_symlink():
        raise EvidenceRejected("unexpected symlink at temp destination")
    with temp.open("wb") as out:
        os.chmod(temp, 0o600)
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


def _new_private_file(path: Path, raw: bytes) -> str:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    return hashlib.sha256(raw).hexdigest()


def _source_proof(geh: Path, sibur: Path) -> dict:
    source_paths = (
        geh / "gpb-geh-section-receipts.json",
        geh / "verified-active-plan.json",
        geh / "guarded-ingest" / "state.json",
        sibur / "receipts.json",
        sibur / "normalized.json",
    )
    result = {}
    for p in source_paths:
        if not p.is_file() or p.is_symlink():
            raise EvidenceRejected(f"source proof unavailable: {p.name}")
        result[p.name] = _sha(p)
    return result


def _run_capture(sibur_root: Path, name: str) -> Path:
    # The only network-bearing path; requires --execute AND --capture-sibur.
    # Cross-report shared source lock prevents two live fetches at once.
    from scripts.research.capture_sibur_public_snapshot import collect
    from src.modules.tender_connectors.sibur.parser import page_url

    u = urlsplit(page_url(1))
    if (u.scheme != "https" or u.hostname != "www.sibur.ru"
            or u.username or u.password or u.port is not None
            or not u.path.startswith("/ru/procurement/buy/")):
        raise EvidenceRejected("SIBUR public collector target allowlist mismatch")
    _safe_dir(sibur_root, create=False)
    lock_path = sibur_root / ".daily-public-capture.lock"
    if lock_path.is_symlink():
        raise EvidenceRejected("SIBUR source lock is a symlink")
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EvidenceRejected("another SIBUR daily source capture is running") from exc
        capture = sibur_root / f"daily-commercial-{name}"
        if capture.exists() or capture.is_symlink():
            raise EvidenceRejected("SIBUR capture name already exists")
        receipt = collect(capture, CAPTURE_MAX_PAGES)
        if (receipt.get("advertised_pages_traversed") is not True
                or receipt.get("errors") != []
                or receipt.get("validated_pages") != receipt.get("announced_pages")):
            raise EvidenceRejected("SIBUR public capture was incomplete")
        return capture
    finally:
        os.close(lock_fd)


def _run_stamp(now: datetime) -> str:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    if not RUN_PATTERN.fullmatch(stamp):
        raise EvidenceRejected("invalid run timestamp")
    return stamp


def _compile(
    *, geh_root: Path, sibur_capture: Path, sibur_watch: Path,
    now: datetime, limit: int,
) -> tuple[dict, Path]:
    geh = latest_geh(geh_root)
    data = compile_watch(
        geh, sibur_watch, now, limit_per_source=limit,
        sibur_current_capture=sibur_capture,
    )
    data["source_paths"] = {
        "geh_snapshot": str(geh),
        "sibur_capture": str(sibur_capture),
    }
    return data, geh


def _report_delta(data: dict, previous: dict | None) -> dict:
    """Changes in the *published shortlist*, not novel source IDs or closures."""
    current = {}
    for source in ("sibur", "geh"):
        for item in data[source]["candidates"]:
            key = source + ":" + item["external_id"]
            current[key] = {
                "deadline_utc": item["deadline_utc"],
                "title": item["title"],
                "price_as_published": item.get("price_as_published"),
            }
    if previous is None:
        return {
            "baseline": "first_run_no_prior_commercial_shortlist",
            "shortlist_added": [],
            "shortlist_changed": [],
            "shortlist_not_recommended_now_not_closure": [],
            "shortlist_size": len(current),
        }
    old = previous.get("shortlist_signature", {})
    if not isinstance(old, dict):
        raise EvidenceRejected("previous commercial receipt has invalid signature structure")
    return {
        "baseline": "prior_successful_shortlist_not_the_entire_source",
        "shortlist_added": sorted(k for k in current if k not in old),
        "shortlist_changed": sorted(k for k in current if k in old and current[k] != old[k]),
        "shortlist_not_recommended_now_not_closure": sorted(k for k in old if k not in current),
        "shortlist_size": len(current),
    }


def _render_delta(delta: dict) -> str:
    lines = [
        "",
        "## Изменения относительно предыдущей коммерческой подборки",
        "Изменения касаются **только выбранных карточек**, а не полного состава закупок.",
    ]
    if delta["baseline"] == "first_run_no_prior_commercial_shortlist":
        lines.append("Первый отчёт: подтверждённого предыдущего сравнения пока нет.")
    else:
        groups = (
            ("Впервые в предыдущем сравнении отобранных карточек", "shortlist_added"),
            ("Изменились срок, название или опубликованная сумма", "shortlist_changed"),
            ("Больше не попали в отобранные карточки — это не означает закрытие", 
             "shortlist_not_recommended_now_not_closure"),
        )
        for label, key in groups:
            entries = delta[key]
            lines.append(f"- {label}: {len(entries)}"
                         + (f" ({', '.join(entries[:15])})" if entries else ""))
    return "\n".join(lines) + "\n"


def _signature(data: dict) -> dict:
    return {
        source + ":" + item["external_id"]: {
            "deadline_utc": item["deadline_utc"],
            "title": item["title"],
            "price_as_published": item.get("price_as_published"),
        }
        for source in ("sibur", "geh")
        for item in data[source]["candidates"]
    }


def _previous_status(out_root: Path) -> dict | None:
    path = out_root / "last_success.json"
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 100000:
        raise EvidenceRejected("previous successful receipt is unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "completed":
        raise EvidenceRejected("previous success receipt invalid")
    return value


def build_report_offline(
    *, geh_root: Path, sibur_capture: Path, sibur_watch: Path,
    now: datetime, limit: int = 14,
) -> dict:
    """No network, file writes or database activity; suitable for inspection/tests."""
    value, _ = _compile(
        geh_root=geh_root, sibur_capture=sibur_capture,
        sibur_watch=sibur_watch, now=now, limit=limit,
    )
    return value


def execute(
    *, geh_root: Path, sibur_root: Path, sibur_watch: Path,
    out_root: Path, now: datetime, limit: int = 14,
    capture_sibur: bool = False, existing_sibur_capture: Path | None = None,
) -> dict:
    """Private output only. Caller must explicitly opt into --execute."""
    if capture_sibur == (existing_sibur_capture is not None):
        raise EvidenceRejected("provide exactly one SIBUR input mode")
    if now.tzinfo is None or not 1 <= limit <= 30:
        raise EvidenceRejected("invalid report timestamp or candidate bound")
    os.umask(0o077)
    out_root = _safe_dir(out_root, create=True)
    lock_path = out_root / ".source-watch.lock"
    if lock_path.is_symlink():
        raise EvidenceRejected("source watch lock is a symlink")
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EvidenceRejected("commercial watch already running") from exc
        stamp = _run_stamp(now)
        attempt = {"run_id": stamp, "started_at": datetime.now(UTC).isoformat(),
                   "status": "in_progress", "capture_sibur": capture_sibur}
        _atomic_private_json(out_root / "last_attempt.json", attempt)
        try:
            if shutil.disk_usage(out_root).free < SPACE_MIN_BYTES:
                raise EvidenceRejected("insufficient safe private storage")
            previous = _previous_status(out_root)
            sb = (_run_capture(sibur_root, stamp) if capture_sibur
                  else existing_sibur_capture)
            assert sb is not None
            data, geh = _compile(
                geh_root=geh_root, sibur_capture=sb,
                sibur_watch=sibur_watch, now=now, limit=limit,
            )
            delta = _report_delta(data, previous)
            data["shortlist_comparison"] = delta
            report_dir = out_root / "runs" / stamp
            _safe_dir(report_dir.parent, create=True)
            _safe_dir(report_dir, create=True)
            data_bytes = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
            text_bytes = (
                render_markdown(data) + "\n" + _render_delta(delta)
            ).encode()
            json_sha = _new_private_file(report_dir / "commercial-watch.json", data_bytes)
            md_sha = _new_private_file(report_dir / "commercial-watch.md", text_bytes)
            receipt = {
                "run_id": stamp, "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "geh_snapshot": str(geh), "sibur_capture": str(sb),
                "source_sha256": _source_proof(geh, sb),
                "report_json_sha256": json_sha,
                "report_markdown_sha256": md_sha,
                "report_json": str(report_dir / "commercial-watch.json"),
                "report_markdown": str(report_dir / "commercial-watch.md"),
                "sibur_relevant": data["sibur"]["summary"].get("unexpired_relevant"),
                "geh_relevant": data["geh"]["summary"].get("matching_unexpired"),
                "shortlist_delta": delta,
                "shortlist_signature": _signature(data),
                "production_database_modified": False,
                "external_submissions_sent": False,
            }
            _new_private_file(
                report_dir / "receipt.json",
                (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode(),
            )
            # Publish last_success *only* after both files and receipt are written.
            _atomic_private_json(out_root / "last_success.json", receipt)
            _atomic_private_json(out_root / "last_attempt.json", receipt)
            return receipt
        except (OSError, ValueError, EvidenceRejected) as exc:
            attempt["status"] = "blocked"
            attempt["error_type"] = type(exc).__name__
            attempt["reason"] = str(exc)[:200]
            attempt["finished_at"] = datetime.now(UTC).isoformat()
            _atomic_private_json(out_root / "last_attempt.json", attempt)
            raise
    finally:
        os.close(fd)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--geh-root", required=True, type=Path)
    p.add_argument("--sibur-root", required=True, type=Path)
    p.add_argument("--sibur-watch", required=True, type=Path)
    p.add_argument("--sibur-current-capture", type=Path,
                   help="Complete existing public SIBUR source (offline, no GET)")
    p.add_argument("--capture-sibur", action="store_true",
                   help="ONLY with --execute: bounded public first-party HTTPS GET")
    p.add_argument("--execute", action="store_true",
                   help="Opt-in private report files and status/lock; never production DB")
    p.add_argument("--out-root", type=Path,
                   help="Private report output, required with --execute")
    p.add_argument("--as-of", default=datetime.now(UTC).isoformat())
    p.add_argument("--limit-per-source", type=int, default=14)
    args = p.parse_args()
    try:
        now = _time(args.as_of)
        if args.execute:
            if args.out_root is None:
                raise EvidenceRejected("--out-root is required with --execute")
            result = execute(
                geh_root=args.geh_root, sibur_root=args.sibur_root,
                sibur_watch=args.sibur_watch,
                out_root=args.out_root, now=now,
                limit=args.limit_per_source,
                capture_sibur=args.capture_sibur,
                existing_sibur_capture=args.sibur_current_capture,
            )
            print(json.dumps(result, ensure_ascii=False))
        else:
            if args.capture_sibur or args.out_root is not None or args.sibur_current_capture is None:
                raise EvidenceRejected("offline mode requires existing --sibur-current-capture")
            data = build_report_offline(
                geh_root=args.geh_root, sibur_capture=args.sibur_current_capture,
                sibur_watch=args.sibur_watch, now=now, limit=args.limit_per_source,
            )
            print(render_markdown(data))
    except (EvidenceRejected, OSError, ValueError) as exc:
        print(f"DAILY_COMMERCIAL_WATCH_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
