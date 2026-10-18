"""Source-first bounded B2B-Center/Workspace snapshot collector, owner-only.

No broad web crawling. A strict public allowlist of exact card URL+ID is the
input. Original HTTP response bytes stay in OWNER PRIVATE ArvectumSSD; only
source SHA, path, source-gate, and observed metadata enter the existing
PostgreSQL learning candidate corpus. CLI is dry-run by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from scripts.procurement_llm.import_candidates import _engine_url
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.modules.procurement_learning_corpus.service import (
    append_candidate,
    make_manual_candidate,
    validate_candidate,
)

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs/roadmap/public_market_collector_pilot_oct18.json"
)
OWNER_PRIVATE = Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent")
MAX_HTML_BYTES = 900_000
MAX_CARDS = 10
NUMBER = re.compile(r"\d{4,7}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class PublicOriginalError(ValueError):
    """Original source missing/ambiguous or unsafe for training candidates."""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _url(card: dict) -> str:
    if not isinstance(card, dict) or set(card) != {"platform", "id", "url"}:
        raise PublicOriginalError("explicit first-party source triplet required")
    platform, number, url = card["platform"], card["id"], card["url"]
    if not isinstance(number, str) or not NUMBER.fullmatch(number):
        raise PublicOriginalError("unexpected source procurement ID")
    if not isinstance(url, str) or len(url) > 650:
        raise PublicOriginalError("invalid original URL")
    p = urlsplit(url)
    if (
        p.scheme != "https" or p.username or p.password or p.query or p.fragment
        or p.port not in (None, 443)
    ):
        raise PublicOriginalError("only first-party public HTTPS original URL")
    if platform == "workspace":
        if p.netloc != "workspace.ru" or not re.fullmatch(
            r"/tenders/[a-z0-9-]+-" + re.escape(number) + r"/", p.path
        ):
            raise PublicOriginalError("Workspace exact tender identity mismatch")
    elif platform == "b2bcenter":
        if p.netloc != "www.b2b-center.ru" or not re.fullmatch(
            r"/(?:app/market-next|market)/[a-z0-9-]+/tender-"
            + re.escape(number) + r"/",
            p.path,
        ):
            raise PublicOriginalError("B2B-Center exact tender identity mismatch")
    else:
        raise PublicOriginalError("not an allowed source platform")
    return url


def validate_manifest(data: object) -> list[dict]:
    if (
        not isinstance(data, dict)
        or set(data) != {"contract_version", "cards"}
        or data["contract_version"] != "public_original_sources_v1"
    ):
        raise PublicOriginalError("unrecognized source manifest schema")
    items = data["cards"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_CARDS:
        raise PublicOriginalError("one to ten explicit public cards required")
    seen = set()
    for item in items:
        _url(item)
        pair = (item["platform"], item["id"])
        if pair in seen:
            raise PublicOriginalError("duplicate exact procurement identity")
        seen.add(pair)
    return items


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PublicOriginalError("unexpected first-party redirect")


def fetch_original(url: str) -> tuple[bytes, str]:
    # Recheck caller-provided public target against exact known source contracts
    # before this function is used by the CLI's controlled allowlist.
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
            final = response.geturl()
            mime = response.headers.get_content_type()
            raw = response.read(MAX_HTML_BYTES + 1)
    except (TimeoutError, OSError, urllib.error.URLError) as exc:
        raise PublicOriginalError("first-party transport unavailable") from exc
    if (
        status != 200 or final != url or mime != "text/html"
        or not 1200 < len(raw) <= MAX_HTML_BYTES
    ):
        raise PublicOriginalError("first-party original response not attestable")
    return raw, mime


def _identity_on_page(card: dict, raw: bytes) -> None:
    try:
        tree = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
        title = " ".join(tree.xpath("//title/text()"))
    except (ValueError, TypeError, html.ParserError) as exc:
        raise PublicOriginalError("HTML parse failed") from exc
    if card["platform"] == "workspace":
        # Visible tender number is not always rendered as text. On this
        # platform the exact canonical + og:url both bind the original ID.
        canonical = tree.xpath("//link[@rel='canonical']/@href")
        og = tree.xpath("//meta[@property='og:url']/@content")
        if canonical != [card["url"]] or og != [card["url"]] or not title.strip():
            raise PublicOriginalError("Workspace original canonical identity unavailable")
    else:
        if not re.search(r"Тендер\s+№\s*" + re.escape(card["id"]) + r"\b", title):
            raise PublicOriginalError("B2B original title tender identity mismatch")


def snapshot_event(card: dict, raw: bytes, observed: datetime, private_path: Path) -> dict:
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise PublicOriginalError("observation time has no timezone")
    _url(card)
    if not isinstance(raw, bytes) or not 1200 < len(raw) <= MAX_HTML_BYTES:
        raise PublicOriginalError("original bytes missing or outside cap")
    _identity_on_page(card, raw)
    original_sha = _digest(raw)
    url_sha = _digest(card["url"].encode("utf-8"))
    seed = f"{card['platform']}:{card['id']}:{url_sha}:{original_sha}"
    event = {
        "event_id": "ta-firstparty:" + _digest(seed.encode())[:40],
        "procurement_ref": card["platform"] + ":" + card["id"],
        "participation": "reviewed_only",
        "review_state": "source_documented",
        "source_role": "development_exposed",
        "event_type": "first_party_public_html_version",
        "source_platform": card["platform"],
        "original_public_url_sha256": url_sha,
        "original_html_response_bytes_sha256": original_sha,
        "original_html_bytes": len(raw),
        "original_http_status": 200,
        "source_snapshot_owner_private_path": str(private_path),
        "source_observed_at_utc": observed.astimezone(UTC).isoformat(),
        "source_gate": "PUBLIC_HTML_ORIGINAL_ATTESTED_NOT_LEGAL_STAGE",
        "buyer_deadline_current_verified": False,
        "full_customer_specification_read": False,
        "platform_account_fee_verified": False,
        "company_bid_eligibility_verified": False,
        "owner_bid_go": False,
        "human_verified_interpretation": False,
        "training_labels": "NOT_REVIEWED",
        "raw_html_bytes_in_db": False,
        "private_chat_in_db": False,
    }
    candidate = make_manual_candidate(event)
    validate_candidate(candidate)
    return candidate


def _private_path(root: Path, card: dict, sha: str) -> Path:
    if root.is_symlink() or not root.is_dir() or not SHA.fullmatch(sha):
        raise PublicOriginalError("owner-only snapshot root unavailable")
    _url(card)
    return root / "original-snapshots" / card["platform"] / card["id"] / (sha + ".html")


def _write_snapshot(path: Path, raw: bytes, root: Path) -> bool:
    # Only allow exact child hierarchy, never user supplied arbitrary path.
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise PublicOriginalError("unsafe snapshot target")
    if path.name != _digest(raw) + ".html":
        raise PublicOriginalError("snapshot SHA and filename mismatch")
    for p in [root / "original-snapshots", path.parent.parent, path.parent]:
        if p.is_symlink():
            raise PublicOriginalError("snapshot parent symlink forbidden")
        if not p.exists():
            p.mkdir(mode=0o700)
        if not p.is_dir():
            raise PublicOriginalError("snapshot parent not directory")
        if stat.S_IMODE(p.stat().st_mode) & 0o077:
            raise PublicOriginalError("snapshot parent too permissive")
    if path.exists():
        if path.read_bytes() != raw or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PublicOriginalError("immutable original snapshot conflict")
        return False
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def _read_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 30_000:
        raise PublicOriginalError("source manifest missing or too large")
    def unique(pairs):
        out = {}
        for key, val in pairs:
            if key in out:
                raise PublicOriginalError("duplicate source manifest JSON key")
            out[key] = val
        return out
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def _preserve_first_observed_payload(session: Session, candidate: dict) -> dict:
    # Identity is source ID + exact raw HTML SHA. Re-observing the SAME bytes
    # must never rewrite immutable provenance: retain the first capture time.
    existing = session.get(
        ProcurementLearningObservation, candidate["observation_id"]
    )
    if existing is None:
        return candidate
    stored = existing.payload_json
    offered = candidate["payload_json"]
    if not isinstance(stored, dict):
        raise PublicOriginalError("stored original event payload is invalid")
    first_seen = stored.get("source_observed_at_utc")
    if not isinstance(first_seen, str):
        raise PublicOriginalError("stored source timestamp is invalid")
    if {k: v for k, v in stored.items() if k != "source_observed_at_utc"} != {
        k: v for k, v in offered.items() if k != "source_observed_at_utc"
    }:
        raise PublicOriginalError("same original content ID has conflicting provenance")
    stable = make_manual_candidate(dict(stored))
    validate_candidate(stable)
    return stable


def collect(cards: list[dict], *, fetch=fetch_original, root: Path = OWNER_PRIVATE,
            observed: datetime | None = None, apply: bool = False,
            engine_factory=None) -> dict:
    cards = validate_manifest({"contract_version": "public_original_sources_v1", "cards": cards})
    observed = observed or datetime.now(UTC)
    # Validate all sources BEFORE the first filesystem/DB write.
    prepared = []
    for card in cards:
        raw, mime = fetch(_url(card))
        if mime != "text/html" or not isinstance(raw, bytes):
            raise PublicOriginalError("transport response MIME not verified")
        _identity_on_page(card, raw)
        path = _private_path(root, card, _digest(raw))
        candidate = snapshot_event(card, raw, observed, path)
        prepared.append((candidate, path, raw))
    if not apply:
        return {
            "mode": "dry_run", "sources": len(prepared),
            "original_http200_pages_checked": len(prepared),
            "snapshot_bytes": sum(len(raw) for _, _, raw in prepared),
            "database_mutations": 0, "private_snapshots_written": 0,
            "training_promotions": 0,
        }
    new_files = []
    try:
        for _, path, raw in prepared:
            if _write_snapshot(path, raw, root):
                new_files.append(path)
        engine = (engine_factory or (lambda: create_engine(_engine_url(), future=True)))()
        try:
            if not inspect(engine).has_table(ProcurementLearningObservation.__tablename__):
                raise RuntimeError("canonical migration 107 missing; refusing write")
            with Session(engine) as session, session.begin():
                added = sum(
                    append_candidate(
                        session, _preserve_first_observed_payload(session, candidate)
                    )
                    for candidate, _, _ in prepared
                )
        finally:
            engine.dispose()
    except BaseException:
        for path in new_files:
            path.unlink(missing_ok=True)
        raise
    return {
        "mode": "existing_arvectum_applied", "sources": len(prepared),
        "inserted": added, "existing": len(prepared) - added,
        "private_snapshots_new": len(new_files), "training_promotions": 0,
        "source_legal_bid_go": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database", choices=["arvectum"])
    args = parser.parse_args()
    if args.apply and args.confirm_database != "arvectum":
        parser.error("explicit --confirm-database arvectum required for source apply")
    cards = validate_manifest(_read_manifest(args.manifest))
    result = collect(cards, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
