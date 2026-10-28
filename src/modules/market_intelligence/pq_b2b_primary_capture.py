"""Read-only exact-number B2B-Center public tender card acquisition.

No guesswork about results: a public archived card may reveal bid counts while
hiding the winning company. Raw HTML (including transient session identifiers)
is protected in existing private runtime and NEVER committed or logged.
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

HOSTS = frozenset({"www.b2b-center.ru", "b2b-center.ru"})
MAX_HTML_BYTES = 400_000
MAX_CARDS = 12
NUM = re.compile(r"[0-9]{7}")
TITLE = re.compile(r"Тендер\s*№\s*([0-9]{7})", re.IGNORECASE)
ORIGINAL_PATH = re.compile(r"/market/[^?]+/tender-([0-9]{7})/")


def _url(url: str) -> urllib.parse.SplitResult:
    p = urllib.parse.urlsplit(url)
    if (p.scheme != "https" or p.hostname not in HOSTS or
            p.port not in (None, 443) or p.username or p.password or p.fragment):
        raise ValueError("B2B-Center requires original HTTPS host")
    return p


def _start_url(number: str) -> str:
    if not isinstance(number, str) or not NUM.fullmatch(number):
        raise ValueError("B2B-Center public tender ID must be seven decimal digits")
    return "https://www.b2b-center.ru/market/view.html?id=" + number


def _final_url(number: str, url: str) -> str:
    p = _url(url)
    match = ORIGINAL_PATH.fullmatch(p.path)
    if not match or match.group(1) != number or p.query:
        raise ValueError("Public ETP page did not bind exact original tender ID")
    return urllib.parse.urlunsplit(("https", p.hostname, p.path, "", ""))


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_original(number: str) -> tuple[bytes, str]:
    start = _start_url(number)
    opener = urllib.request.build_opener(_SameHostRedirect())
    request = urllib.request.Request(start, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ArvectumResearch/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    })
    with opener.open(request, timeout=13) as reply:
        if (reply.status != 200 or "text/html" not in
                (reply.headers.get("Content-Type") or "").lower()):
            raise ValueError("B2B-Center did not return a public original HTML page")
        url = _final_url(number, reply.url)
        blob = reply.read(MAX_HTML_BYTES + 1)
    if len(blob) > MAX_HTML_BYTES or not blob.lstrip().lower().startswith(b"<!doctype html"):
        raise ValueError("Unrecognized or oversized B2B-Center original HTML")
    return blob, url


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.tokens: list[str] = []
        self._title = False
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "template"}:
            self._hidden += 1
        if tag == "title":
            self._title = True
        if tag == "meta":
            attr = dict(attrs)
            if attr.get("name") == "description":
                self.description = (attr.get("content") or "")[:4000]

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "template"}:
            self._hidden = max(self._hidden - 1, 0)
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title += data[:800]
        if not self._hidden and len(self.tokens) < 30000:
            self.tokens.append(data)


def _normal(value: str) -> str:
    return " ".join(value.split())


def _parse(number: str, blob: bytes) -> dict:
    page = _Page()
    page.feed(blob.decode("utf-8", errors="replace"))
    title = _normal(page.title)
    description = _normal(page.description)
    visible = _normal(" ".join(page.tokens))
    found = TITLE.search(title)
    if not found or found.group(1) != number:
        raise ValueError("Original B2B title does not bind supplied tender number")
    search = (title + " " + description).casefold()
    if not any(term in search for term in (
            "укрм", "аукрм", "статком", "конденсатор", "компенсац", "фильтр гармоник")):
        raise ValueError("Original B2B tender card has no Power Quality evidence")
    organizer = re.search(r"Организатор:\s*(.{1,160}?)\s+Заказчики:", visible)
    buyer = re.search(r"Заказчики:\s*(.{1,250}?)\s+Дополнительная информация", visible)
    bids = re.search(r"Всего заявок:\s*(\d+)", visible)
    status = re.search(r"Статус объявления:\s*([^.]{1,90})\.", visible)
    replaced = re.search(r"взамен конкурса\s*№\s*(\d{7})", title, re.IGNORECASE)
    hidden = "Результаты процедуры скрыты по решению ее организатора" in visible
    return {
        "source_title": title,
        "source_description": description,
        "organizer_platform_display": _normal(organizer.group(1)) if organizer else None,
        "buyer_platform_display": _normal(buyer.group(1)) if buyer else None,
        "platform_status_text": _normal(status.group(1)) if status else None,
        "applications_count_not_qualified_bidders": int(bids.group(1)) if bids else None,
        "results_hidden_by_organizer": hidden,
        "replaces_reference_in_original_title": replaced.group(1) if replaced else None,
        "subject_category": (
            "maintenance_of_installed_equipment"
            if ("техническое обслуживание" in search or "техобслуживание" in search)
            else "procurement_or_supply_inquiry_no_award_confirmed"
        ),
    }


def _atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     prefix=".b2b-", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def capture(*, number: str, root: Path, fetch=fetch_original) -> dict:
    _start_url(number)
    if root.is_symlink():
        raise ValueError("Unsafe original public source root")
    directory = root / number
    if directory.is_symlink():
        raise ValueError("Symlinked B2B original source folder")
    receipt = directory / "receipt.json"
    original = directory / "original-public-b2b.html"
    if receipt.is_file():
        if receipt.is_symlink() or original.is_symlink() or not original.is_file():
            raise ValueError("Unsafe source receipt")
        record = json.loads(receipt.read_text(encoding="utf-8"))
        if (record.get("procedure_id") != number
                or hashlib.sha256(original.read_bytes()).hexdigest() != record.get("original_html_sha256")
                or _final_url(number, record.get("source_url") or "") != record.get("source_url")):
            raise ValueError("Existing first-party B2B receipt is invalid")
        return record
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("Nonempty source directory without verified receipt")
    blob, actual_url = fetch(number)
    final_url = _final_url(number, actual_url)
    if len(blob) > MAX_HTML_BYTES or not blob.lstrip().lower().startswith(b"<!doctype html"):
        raise ValueError("Unsafe B2B source size or format")
    details = _parse(number, blob)
    directory.mkdir(parents=True, exist_ok=True)
    with original.open("xb") as stream:
        stream.write(blob)
    original.chmod(0o600)
    record = {
        "schema_version": "pq-original-b2b-public-card/1",
        "procedure_id": number,
        "source_url": final_url,
        "source_tier": "original_primary_b2b_public_html",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "original_html_sha256": hashlib.sha256(blob).hexdigest(),
        "original_html_bytes": len(blob),
        **details,
        "winner_verified": False,
        "signed_contract_verified": False,
        "signed_contract_supplier": None,
        "contract_price_rub": None,
    }
    _atomic(receipt, record)
    return record


def _b2b_eligible(row: dict) -> bool:
    number = str(row.get("procedure_id") or "")
    if not NUM.fullmatch(number):
        return False
    for item in row.get("evidence") or []:
        url = item.get("url") or ""
        if isinstance(url, str) and (
                "/zakupki/b2b/" + number in url.casefold()
                or "/market/view.html?id=" + number in url.casefold()
                or ("/tender-" + number + "/") in url.casefold()):
            return True
    return False


def batch(*, leads: Path, root: Path, journal: Path,
          max_cards: int = 4, retry_hours: int = 12,
          fetch=fetch_original) -> dict:
    if not 1 <= max_cards <= MAX_CARDS or not 1 <= retry_hours <= 720:
        raise ValueError("Unbounded B2B original-card discovery")
    data = json.loads(leads.read_text(encoding="utf-8"))["records"]
    state = json.loads(journal.read_text(encoding="utf-8")) if journal.is_file() else {
        "schema_version": "pq-original-b2b-capture-attempts/1", "attempts": []}
    if state.get("schema_version") != "pq-original-b2b-capture-attempts/1":
        raise ValueError("Invalid durable B2B source journal")
    latest = {x["procedure_id"]: x for x in state["attempts"]}
    now = datetime.now(timezone.utc)
    processed = []
    for row in data:
        if len(processed) >= max_cards:
            break
        if not _b2b_eligible(row):
            continue
        number = str(row["procedure_id"])
        previous = latest.get(number)
        if previous:
            try:
                if (now - datetime.fromisoformat(previous["timestamp"])).total_seconds() < retry_hours * 3600:
                    continue
            except (ValueError, KeyError, TypeError):
                pass
        try:
            result = capture(number=number, root=root, fetch=fetch)
            outcome = {"status": "original_primary_html_verified",
                       "original_html_sha256": result["original_html_sha256"]}
        except (ValueError, OSError, RuntimeError, urllib.error.URLError) as exc:
            outcome = {"status": "original_unavailable_or_invalid",
                       "error_type": type(exc).__name__}
        event = {"procedure_id": number, "timestamp": now.isoformat(), **outcome}
        state["attempts"].append(event)
        processed.append(event)
        _atomic(journal, state)
    return {
        "attempted": len(processed),
        "first_party_original_cards_verified": sum(
            x["status"] == "original_primary_html_verified" for x in processed),
        "results": processed,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-cards", type=int, default=4)
    args = p.parse_args()
    report = batch(leads=args.leads, root=args.root,
                   journal=args.journal, max_cards=args.max_cards)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
