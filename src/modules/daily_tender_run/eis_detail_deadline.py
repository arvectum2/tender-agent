"""Bounded, evidence-preserving public EIS exact-deadline verification.

Date-only EIS summary values must never turn into an invented midnight.
Only a detailed official notice with an explicit regional Moscow offset
and a saved private original supplies a precise deadline for a new run.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

HOST = "zakupki.gov.ru"
PATH_RE = re.compile(r"^/epz/order/notice/(?:ea20|zk20|ok20)/view/common-info\.html$")
REGISTRY_RE = re.compile(r"^\d{19}$")
RUN_ID_RE = re.compile(r"^DTR-\d{8}T\d{6}Z-[a-f0-9]{8}$")
TITLE_RE = re.compile(
    r"<span[^>]*class=['\"][^'\"]*section__title[^'\"]*['\"][^>]*>"
    r"\s*Дата и время окончания срока подачи заявок\s*</span>",
    re.IGNORECASE | re.DOTALL,
)
VALUE_RE = re.compile(
    r"<span[^>]*class=['\"][^'\"]*section__info[^'\"]*['\"][^>]*>"
    r"\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})",
    re.IGNORECASE | re.DOTALL,
)
ZONE_RE = re.compile(r"\(МСК\s*([+-]\d{1,2})?\)", re.IGNORECASE)
MAX_HTML_BYTES = 6 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 9


@dataclass(frozen=True)
class EISDeadlineProof:
    deadline_utc: datetime
    official_timezone: str
    original_sha256: str
    checked_at_utc: datetime


class EISProofError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _official_url(url: str, registry_number: str) -> str:
    if not isinstance(url, str) or not REGISTRY_RE.fullmatch(registry_number):
        raise EISProofError("invalid EIS number")
    u = urllib.parse.urlsplit(url)
    if (
        u.scheme != "https"
        or u.hostname != HOST
        or u.username is not None
        or u.password is not None
        or u.port is not None
        or not PATH_RE.fullmatch(u.path)
        or u.fragment
        or urllib.parse.parse_qs(u.query) != {"regNumber": [registry_number]}
    ):
        raise EISProofError("untrusted or unmatched EIS source URL")
    return url


def parse_official_detail(page: str, registry_number: str) -> tuple[datetime, str]:
    """Parse the detailed exact clock field with explicitly displayed timezone."""
    if not REGISTRY_RE.fullmatch(registry_number) or not re.search(
        rf"(?<!\d){re.escape(registry_number)}(?!\d)", page
    ):
        raise EISProofError("unmatched EIS HTML identity")
    matches = list(TITLE_RE.finditer(page))
    if len(matches) != 1:
        raise EISProofError("missing or ambiguous exact EIS deadline field")
    section = page[matches[0].end() : matches[0].end() + 850]
    date_match = VALUE_RE.search(section)
    zone_match = ZONE_RE.search(re.sub(r"<[^>]*>", " ", section[:460]))
    if not date_match or date_match.start() > 140 or not zone_match:
        raise EISProofError("exact EIS date/clock/timezone not verified")
    hours = int(zone_match.group(1)) if zone_match.group(1) else 0
    if not -1 <= hours <= 9:
        raise EISProofError("unsupported regional timezone")
    try:
        parsed = datetime.strptime(
            f"{date_match.group(1)} {date_match.group(2)}", "%d.%m.%Y %H:%M"
        ).replace(tzinfo=timezone(timedelta(hours=3 + hours)))
    except ValueError as exc:
        raise EISProofError("invalid detailed EIS date/time") from exc
    return parsed.astimezone(UTC), "МСК" + (f"{hours:+d}" if hours else "")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _private_directory(path: Path, *, create: bool) -> None:
    if path.is_symlink():
        raise EISProofError("symlink evidence folder")
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    if (not path.is_dir() or path.stat().st_uid != os.getuid()
            or path.stat().st_mode & 0o077):
        raise EISProofError("untrusted evidence folder")


def _save_original(
    root: Path,
    run_id: str,
    registry_number: str,
    raw: bytes,
    proof: EISDeadlineProof,
    url: str,
) -> None:
    if not RUN_ID_RE.fullmatch(run_id):
        raise EISProofError("invalid Daily Tender run ID")
    _private_directory(root, create=False)
    folder = root / run_id
    _private_directory(folder, create=True)
    receipt = {
        "registry_number": registry_number,
        "run_id": run_id,
        "source_url": url,
        "deadline_utc": proof.deadline_utc.isoformat(),
        "official_timezone": proof.official_timezone,
        "html_sha256": proof.original_sha256,
        "bytes": len(raw),
        "checked_at_utc": proof.checked_at_utc.isoformat(),
    }
    original_path = folder / f"{registry_number}.html"
    receipt_path = folder / f"{registry_number}.json"
    if receipt_path.exists() and not receipt_path.is_symlink():
        try:
            prior = json.loads(receipt_path.read_text())
        except (OSError, ValueError) as exc:
            raise EISProofError("archived receipt cannot be verified") from exc
        # Idempotent retry of the *same* original must not falsely report a
        # change just because the new HTTP GET has a later checked_at value.
        expected = {key: value for key, value in receipt.items() if key != "checked_at_utc"}
        observed = {key: value for key, value in prior.items() if key != "checked_at_utc"}
        if observed != expected:
            raise EISProofError("archived official source changed within the same run")
        receipt = prior
    for file, content in (
        (original_path, raw),
        (receipt_path,
         (json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n").encode()),
    ):
        if file.is_symlink():
            raise EISProofError("symlink evidence file")
        if file.exists():
            if (not file.is_file() or file.stat().st_mode & 0o077
                    or file.stat().st_uid != os.getuid() or file.read_bytes() != content):
                raise EISProofError("existing EIS original differs")
            continue
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())


def verify_official_eis_deadline(
    source_url: str | None,
    registry_number: str,
    run_id: str,
    *,
    evidence_root: Path | None = None,
) -> tuple[EISDeadlineProof | None, str]:
    """Return evidence or a bounded failure code, never an unverified instant."""
    if evidence_root is None:
        configured = os.environ.get("ARVECTUM_DAILY_EIS_EVIDENCE_ROOT", "").strip()
        if not configured:
            return None, "deadline_eis_evidence_archive_not_configured"
        evidence_root = Path(configured)
    try:
        url = _official_url(source_url or "", registry_number)
        if not RUN_ID_RE.fullmatch(run_id):
            raise EISProofError("invalid run identity")
        _private_directory(evidence_root, create=False)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
            method="GET",
        )
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            if (response.status != 200
                    or "html" not in response.headers.get("Content-Type", "").lower()):
                raise EISProofError("official EIS is not HTML 200")
            raw = response.read(MAX_HTML_BYTES + 1)
        if len(raw) > MAX_HTML_BYTES:
            raise EISProofError("official EIS exceeded read cap")
        exact_utc, zone = parse_official_detail(raw.decode("utf-8", "replace"), registry_number)
        proof = EISDeadlineProof(exact_utc, zone, _sha(raw), datetime.now(UTC))
        _save_original(evidence_root, run_id, registry_number, raw, proof, url)
        return proof, "deadline_eis_exact_source_verified"
    except (OSError, ValueError, urllib.error.URLError):
        return None, "deadline_eis_exact_source_unverified"
