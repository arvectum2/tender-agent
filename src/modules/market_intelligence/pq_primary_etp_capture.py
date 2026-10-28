"""Public-first Bidzaar ETP cards: exact-ID verified HTML evidence, no API guesses.

Only owner-supplied v29 original-platform URLs qualify. Archived HTML is
immutable source evidence, not trusted instructions; no authentication,
bidding, or speculative public attachment link construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
MAX_HTML_BYTES = 900_000
MAX_CARDS = 12


def _validated_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 320:
        raise ValueError("Invalid ETP original-card URL")
    u = urllib.parse.urlsplit(url)
    if (u.scheme != "https" or u.hostname != "bidzaar.com" or u.port not in (None, 443)
            or u.username or u.password or u.query or u.fragment):
        raise ValueError("ETP card host or URL properties invalid")
    prefix = "/app/process/light/"
    if not u.path.startswith(prefix) or not UUID.fullmatch(u.path[len(prefix):]):
        raise ValueError("ETP card URL must contain exact public UUID")
    return f"https://bidzaar.com{u.path}"


class _StrictRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _validated_url(newurl) != _validated_url(req.full_url):
            raise urllib.error.URLError("redirect_changed_etp_identity")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_public_html(url: str) -> tuple[bytes, str]:
    url = _validated_url(url)
    opener = urllib.request.build_opener(_StrictRedirect())
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ArvectumTenderResearch/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with opener.open(req, timeout=15) as response:
        if response.status != 200 or "text/html" not in (
                response.headers.get("Content-Type") or "").lower():
            raise ValueError("Source returned non-HTML or non-200 response")
        if _validated_url(response.url) != url:
            raise ValueError("Source redirected from original public card")
        blob = response.read(MAX_HTML_BYTES + 1)
    if len(blob) > MAX_HTML_BYTES or not blob.lstrip().lower().startswith(b"<!doctype html"):
        raise ValueError("Invalid original HTML resource or response budget")
    return blob, url


class MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.props: dict[str, str] = {}
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            value = attributes.get("content")
            if key in {"og:url", "og:title", "description", "og:description"} and value:
                self.props[key] = value[:10_000]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data[:5_000]


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".etp-", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def capture(*, number: str, url: str, source_root: Path,
            fetch: Callable[[str], tuple[bytes, str]] = fetch_public_html) -> dict:
    if not isinstance(number, str) or not re.fullmatch(r"[0-9]{1,6}-[0-9]{1,6}", number):
        raise ValueError("Unexpected commercial procurement number")
    source_url = _validated_url(url)
    slug = source_url.rsplit("/", 1)[-1]
    case = source_root / slug
    if source_root.is_symlink() or case.is_symlink():
        raise ValueError("Symlinked source root")
    receipt = case / "receipt.json"
    html_file = case / "original-public-etp.html"
    if receipt.exists():
        if receipt.is_symlink() or html_file.is_symlink() or not html_file.is_file():
            raise ValueError("Unsafe existing original ETP receipt")
        old = json.loads(receipt.read_text(encoding="utf-8"))
        if (old.get("procedure_id") != number or old.get("source_url") != source_url
                or hashlib.sha256(html_file.read_bytes()).hexdigest() != old.get("original_html_sha256")):
            raise ValueError("Original ETP card receipt changed or mismatched")
        return old
    if case.exists() and any(case.iterdir()):
        raise ValueError("ETP original-card folder exists without receipt")
    blob, returned_url = fetch(source_url)
    if _validated_url(returned_url) != source_url or len(blob) > MAX_HTML_BYTES:
        raise ValueError("ETP card redirected or response budget exceeded")
    parser = MetaParser()
    parser.feed(blob.decode("utf-8", errors="replace"))
    title = " ".join(parser.title.split())
    description = " ".join((parser.props.get("description") or "").split())
    expected = re.compile(r"(?i)^Тендер\s+" + re.escape(number) + r"\s+[—–-]\s+")
    if (not expected.search(title)
            or not description
            or parser.props.get("og:url") != source_url):
        raise ValueError("Original ETP page metadata does not bind exact card/notice")
    pq_text = (title + " " + description).casefold()
    if not (any(word in pq_text for word in (
            "компенсац", "конденсатор", "укрм"))
            or ("гармоник" in pq_text and "фильтр" in pq_text)):
        raise ValueError("Original ETP card has no Power Quality source evidence")
    sha = hashlib.sha256(blob).hexdigest()
    case.mkdir(parents=True, exist_ok=True)
    with html_file.open("xb") as stream:
        stream.write(blob)
    html_file.chmod(0o600)
    report = {
        "schema_version": "pq-public-primary-etp/1",
        "procedure_id": number,
        "source_url": source_url,
        "source_tier": "original_public_primary_etp",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "original_html_sha256": sha,
        "original_html_bytes": len(blob),
        "source_title": title,
        "source_description": description[:4_000],
        "metadata_exact_notice_verified": True,
        "source_evidence_verified": True,
        "source_attachment_downloaded": False,
        "winner_verified": False,
        "signed_contract_verified": False,
        "signed_contract_amount_rub": None,
        "proven_market_volume_rub": None,
    }
    _atomic_json(receipt, report)
    return report


def batch(*, leads: Path, source_root: Path, journal: Path,
          max_cards: int = 4, retry_hours: int = 12,
          fetch: Callable[[str], tuple[bytes, str]] = fetch_public_html) -> dict:
    if not 1 <= max_cards <= MAX_CARDS or not 1 <= retry_hours <= 720:
        raise ValueError("Invalid primary ETP budget")
    corpus = json.loads(leads.read_text(encoding="utf-8"))["records"]
    old = json.loads(journal.read_text(encoding="utf-8")) if journal.is_file() else {
        "schema_version": "pq-etp-primary-attempts/1", "attempts": []}
    if old.get("schema_version") != "pq-etp-primary-attempts/1":
        raise ValueError("Unknown ETP primary journal")
    now = datetime.now(timezone.utc)
    recent = {a["source_url"]: a for a in old["attempts"]}
    attempts = []
    seen: set[str] = set()
    for row in corpus:
        if len(attempts) >= max_cards:
            break
        number = str(row.get("procedure_id") or "")
        for ev in row.get("evidence") or []:
            url = ev.get("url")
            if not isinstance(url, str) or "bidzaar.com" not in url or url in seen:
                continue
            seen.add(url)
            try:
                canonical_url = _validated_url(url)
            except ValueError:
                continue
            previous = recent.get(canonical_url)
            if previous:
                try:
                    if (now - datetime.fromisoformat(previous["timestamp"])).total_seconds() < retry_hours * 3600:
                        continue
                except (KeyError, ValueError, TypeError):
                    pass
            try:
                receipt = capture(number=number, url=canonical_url,
                                  source_root=source_root, fetch=fetch)
                result = {"status": "original_verified",
                          "original_html_sha256": receipt["original_html_sha256"],
                          "exact_id": receipt["metadata_exact_notice_verified"]}
            except (ValueError, OSError, urllib.error.URLError) as exc:
                result = {"status": "source_failed", "error_type": type(exc).__name__}
            entry = {"timestamp": now.isoformat(), "procedure_id": number,
                     "source_url": canonical_url, **result}
            old["attempts"].append(entry)
            recent[canonical_url] = entry
            attempts.append(entry)
            _atomic_json(journal, old)
            if len(attempts) >= max_cards:
                break
    return {"attempts": len(attempts),
            "source_cards_verified": sum(x["status"] == "original_verified" for x in attempts),
            "total_journal_entries": len(old["attempts"]),
            "results": attempts}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cards", type=int, default=4)
    args = p.parse_args()
    print(json.dumps(batch(leads=args.leads, source_root=args.source_root,
                           journal=args.journal, max_cards=args.max_cards),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
