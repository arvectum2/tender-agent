"""Read-only exact EIS deadline evidence auditor for a previously pinned DB snapshot.

Source-only HTTPS GET to explicitly stored notice URLs. No DB connection,
credential, portal POST, status mutation or automatic historical deadline rewrite.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import hashlib
import html
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

OFFICIAL_HOST = "zakupki.gov.ru"
OFFICIAL_PATH = re.compile(
    r"^/epz/order/notice/(?:ea20|zk20|ok20)/view/common-info\.html$"
)
NOTICE_NUMBER = re.compile(r"^\d{19}$")
EXACT_FIELD = "Дата и время окончания срока подачи заявок"
FIELD_TITLE = re.compile(
    r"<span[^>]*class=['\"][^'\"]*section__title[^'\"]*['\"][^>]*>"
    r"\s*Дата и время окончания срока подачи заявок\s*</span>",
    re.IGNORECASE | re.DOTALL,
)
FIELD_VALUE = re.compile(
    r"<span[^>]*class=['\"][^'\"]*section__info[^'\"]*['\"][^>]*>"
    r"\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)
TIMEZONE = re.compile(r"\(МСК\s*([+-]\d{1,2})?\)", re.IGNORECASE)
MAX_HTML = 1_700_000
MAX_SNAPSHOT = 2_000_000
MIN_REQUEST_INTERVAL = 0.85
AUDIT_AGENT = "Mozilla/5.0 (Arvectum procurement evidence read-only)"
SOURCE_MOSCOW = timezone(timedelta(hours=3))


class ProofFailure(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_private_dir(path: Path, create: bool) -> None:
    if path.is_symlink():
        raise ProofFailure("symlink output directory")
    if create and not path.exists():
        path.mkdir(mode=0o700, parents=False)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise ProofFailure(f"unsafe private directory {path.name}")


def _unique_notice_url(raw: str, registry: str) -> str:
    if not isinstance(raw, str) or not NOTICE_NUMBER.fullmatch(registry):
        raise ProofFailure("untrusted source notice identity")
    u = urllib.parse.urlsplit(raw)
    query = urllib.parse.parse_qs(u.query)
    if (u.scheme != "https" or u.hostname != OFFICIAL_HOST
            or u.username or u.password or u.port is not None
            or not OFFICIAL_PATH.fullmatch(u.path) or u.fragment
            or query != {"regNumber": [registry]}):
        raise ProofFailure("non-official or unmatched source URL")
    return raw


def _read_snapshot(path: Path, expected_sha: str) -> tuple[dict, dict[str, list[dict]]]:
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > MAX_SNAPSHOT or digest(path) != expected_sha):
        raise ProofFailure("production DB read-only snapshot SHA mismatch")
    data = json.loads(path.read_text())
    if (data.get("metadata", {}).get("midnight_rows") != 298 or
            data["metadata"].get("distinct_registry") != 196 or
            data["metadata"].get("isolation") != "repeatable_read_read_only" or
            len(data.get("records", [])) != 298):
        raise ProofFailure("production snapshot is incomplete or wrong scope")
    groups: dict[str, list[dict]] = {}
    seen_rows = set()
    for row in data["records"]:
        registry = row["registry_number"]
        _unique_notice_url(row["source_url"], registry)
        if (row["id"] in seen_rows or row.get("source") != "public_eis_html_44fz"
                or row.get("law") != "44fz" or
                not row["stored_deadline_msk"].endswith("+03:00") or
                row["stored_deadline_msk"][11:19] != "00:00:00"):
            raise ProofFailure("snapshot EIS source or midnight invariant mismatch")
        seen_rows.add(row["id"])
        groups.setdefault(registry, []).append(row)
    if len(groups) != 196:
        raise ProofFailure("unexpected number of distinct EIS notices")
    return data, groups


def extract_exact_eis_deadline(page_html: str, registry: str) -> dict:
    """Extract the *detailed official* field and its displayed timezone.

    Date-only summary cards are never interpreted as midnight. Regional
    labels such as МСК-1 or МСК+7 are converted to UTC explicitly.
    """
    if not isinstance(page_html, str) or registry not in page_html:
        raise ProofFailure("official HTML does not identify requested registry")
    matches = list(FIELD_TITLE.finditer(page_html))
    if len(matches) != 1:
        raise ProofFailure("exact deadline field missing or repeated")
    body = page_html[matches[0].end():matches[0].end() + 850]
    val = FIELD_VALUE.search(body)
    if not val or val.start() > 140:
        raise ProofFailure("exact detailed field has no clock")
    tzmatch = TIMEZONE.search(html.unescape(re.sub(r"<[^>]+>", " ", body[:460])))
    if not tzmatch:
        raise ProofFailure("official timezone label missing")
    raw_offset = tzmatch.group(1)
    offset = int(raw_offset) if raw_offset else 0
    if not -1 <= offset <= 9:
        raise ProofFailure("unsupported official regional time offset")
    try:
        local = datetime.strptime(f"{val.group(1)} {val.group(2)}", "%d.%m.%Y %H:%M")
        local = local.replace(tzinfo=timezone(timedelta(hours=3 + offset)))
    except ValueError as exc:
        raise ProofFailure("invalid date in official detailed field") from exc
    return {
        "official_field": EXACT_FIELD,
        "official_printed_date": val.group(1),
        "official_printed_time": val.group(2),
        "official_timezone": "МСК" + (f"{offset:+d}" if offset else ""),
        "official_utc": local.astimezone(UTC).isoformat(),
        "official_msk": local.astimezone(SOURCE_MOSCOW).isoformat(),
    }


def _write_exclusive(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _save_result(path: Path, record: dict) -> None:
    _write_exclusive(path, (json.dumps(record, ensure_ascii=False, sort_keys=True,
                                       indent=2) + "\n").encode())


def _fetch(url: str, registry: str) -> dict:
    _unique_notice_url(url, registry)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": AUDIT_AGENT, "Accept": "text/html"}, method="GET"
    )
    with opener.open(request, timeout=9) as response:
        if response.status != 200:
            raise ProofFailure("official endpoint non-200 response")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ProofFailure("official endpoint non-HTML response")
        raw = response.read(MAX_HTML + 1)
    if len(raw) > MAX_HTML:
        raise ProofFailure("official HTML exceeds bounded limit")
    return {"raw": raw, "html": raw.decode("utf-8", "replace"), "status": 200}


def _priority(group: list[dict]) -> tuple:
    status = {r["status"] for r in group}
    priorities = {"MANAGER_READY": 0, "FAILED": 1, "SUPERSEDED": 2,
                  "DUPLICATE": 3, "SCREENED_OUT": 4}
    best = min((priorities.get(s, 5) for s in status), default=5)
    return (best, max(r["stored_deadline_msk"] for r in group))


def audit_batch(snapshot: Path, expected_sha: str, root: Path, limit: int) -> dict:
    if not 1 <= limit <= 45:
        raise ProofFailure("request limit outside safe bounds")
    _safe_private_dir(root, False)
    data, groups = _read_snapshot(snapshot, expected_sha)
    for sub in ("html", "receipts"):
        _safe_private_dir(root / sub, True)
    lock_path = root / ".source-audit.lock"
    if lock_path.is_symlink():
        raise ProofFailure("audit lock is a symlink")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = sorted(
            (k for k in groups if not (root / "receipts" / f"{k}.json").exists()),
            key=lambda k: (_priority(groups[k]), k),
        )
        selected = pending[:limit]
        pace_lock = threading.Lock()
        last_request = [0.0]
        stop_on_rate_limit = threading.Event()

        def handle(registry: str) -> dict:
            rows = groups[registry]
            urls = {r["source_url"] for r in rows}
            result = {
                "registry_number": registry,
                "row_count": len(rows),
                "database_row_ids": [r["id"] for r in rows],
                "stored_deadline_utc": sorted({r["deadline_at"] for r in rows}),
                "stored_deadline_msk": sorted({r["stored_deadline_msk"] for r in rows}),
                "business_statuses": sorted({r["status"] for r in rows}),
                "audited_at_utc": datetime.now(UTC).isoformat(),
                "status": "unverified",
            }
            if len(urls) != 1:
                result.update(status="ambiguous_source_urls")
            elif stop_on_rate_limit.is_set():
                result.update(status="rate_limited_unchecked")
            else:
                url = next(iter(urls))
                result["source_url"] = url
                original = root / "html" / f"{registry}.html"
                raw = None
                if original.exists():
                    if original.is_symlink() or original.stat().st_size > MAX_HTML:
                        result.update(status="invalid_preserved_source")
                    else:
                        raw = original.read_bytes()
                else:
                    try:
                        with pace_lock:
                            remaining = MIN_REQUEST_INTERVAL - (time.monotonic() - last_request[0])
                            if remaining > 0:
                                time.sleep(remaining)
                            last_request[0] = time.monotonic()
                        payload = _fetch(url, registry)
                        raw = payload["raw"]
                        _write_exclusive(original, raw)
                        result["http_status"] = 200
                    except urllib.error.HTTPError as exc:
                        result.update(status="http_unavailable", http_status=exc.code)
                        if exc.code == 429:
                            stop_on_rate_limit.set()
                    except (TimeoutError, OSError, urllib.error.URLError) as exc:
                        result.update(status="network_unavailable", error_type=type(exc).__name__)
                    except ProofFailure as exc:
                        result.update(status="invalid_official_source", reason=str(exc))
                if raw is not None:
                    result["source_html_sha256"] = hashlib.sha256(raw).hexdigest()
                    result["source_html_bytes"] = len(raw)
                    try:
                        parsed = extract_exact_eis_deadline(raw.decode("utf8", "replace"), registry)
                        result.update(parsed)
                        official = datetime.fromisoformat(parsed["official_utc"])
                        stored = [datetime.fromisoformat(x["deadline_at"]) for x in rows]
                        matches = [t == official for t in stored]
                        result["exactly_matching_rows"] = sum(matches)
                        result["mismatching_rows"] = len(stored) - sum(matches)
                        result["status"] = "official_exact_verified"
                    except ProofFailure as exc:
                        result.update(status="exact_field_unavailable", reason=str(exc))
            _save_result(root / "receipts" / f"{registry}.json", result)
            return {"registry": registry, "status": result["status"],
                    "rows": result["row_count"], "match": result.get("exactly_matching_rows")}

        # At most two network workers + globally capped source request interval.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            done = list(pool.map(handle, selected))
        counts = Counter(x["status"] for x in done)
        receipts = list((root / "receipts").glob("*.json"))
        print(json.dumps({
            "batch": len(selected), "completed_unique": len(receipts),
            "remaining_unique": len(groups) - len(receipts),
            "batch_statuses": dict(counts),
            "batch_rows": sum(x["rows"] for x in done),
            "batch_matches": sum(x.get("match") or 0 for x in done),
            "source_sha256": expected_sha,
        }, ensure_ascii=False))
        return {"processed": len(selected), "remaining": len(groups) - len(receipts)}
    finally:
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()
    try:
        audit_batch(args.snapshot, args.expected_sha256, args.root, args.limit)
    except (ProofFailure, OSError, ValueError, BlockingIOError) as exc:
        parser.exit(2, f"EIS AUDIT BLOCKED: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
