"""Bounded public procurement card audit across known ETP and mirror URLs.

Only probes URLs present in the source retrieval queue. No guessed URLs,
automatic bidding or claim that aggregator pricing is a signed award.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ALLOW = frozenset({"poisktenderov.ru","zakupki.tochka.com","synapsenet.ru",
                   "uds-group.ru","b2b.house","energybase.ru","zakupki.kontur.ru",
                   "tendik.ru"})
PRIMARY = frozenset({"uds-group.ru"})
MAX_HTML_BYTES = 512 * 1024


class _StrictRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname != urllib.parse.urlsplit(req.full_url).hostname:
            raise urllib.error.URLError("cross-host redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_direct_verified_tls(url: str, *, timeout: int = 10) -> dict:
    """Bounded direct-HTTPS fallback for a proxy transport failure, never 401/403.

    curl verifies the server certificate by default. No redirects, credentials,
    insecure TLS flags or guessed attachment URLs are permitted.
    """
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOW
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Not an allowlisted HTTPS source")
    with tempfile.TemporaryDirectory(prefix="pq-etp-direct-") as directory:
        body = Path(directory) / "body"
        headers = Path(directory) / "headers"
        try:
            process = subprocess.run([
                "curl", "--noproxy", "*", "--proto", "=https",
                "--max-time", str(timeout), "--max-filesize", str(MAX_HTML_BYTES),
                "--silent", "--show-error", "--dump-header", str(headers),
                "--output", str(body), "--write-out",
                "%{http_code}|%{ssl_verify_result}|%{url_effective}", url,
            ], capture_output=True, text=True, timeout=timeout + 3, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise urllib.error.URLError("direct TLS transport unavailable") from exc
        fields = process.stdout.strip().split("|")
        code = int(fields[0]) if fields and fields[0].isdigit() else 0
        if (len(fields) != 3 or fields[1] != "0" or fields[2] != url
                or process.returncode not in (0, 56, 63)):
            raise urllib.error.URLError("direct TLS validation failed")
        if code in (401, 403):
            return {"status": "inaccessible", "http_status": code}
        if code == 404:
            return {"status": "not_found", "http_status": code}
        if code != 200:
            return {"status": "retryable_http_error" if code in (408, 429, 500, 502, 503, 504)
                    else "http_error", "http_status": code}
        if (process.returncode == 63 or
                (body.exists() and body.stat().st_size > MAX_HTML_BYTES) or
                (process.returncode == 56 and body.exists()
                 and body.stat().st_size >= MAX_HTML_BYTES)):
            return {"status": "body_budget_exceeded", "http_status": code}
        if process.returncode != 0:
            raise urllib.error.URLError("incomplete direct TLS response")
        if not body.is_file() or not headers.is_file():
            raise urllib.error.URLError("missing direct TLS response")
        typ = headers.read_text(encoding="utf-8", errors="replace").lower()
        if "text/html" not in typ:
            return {"status": "non_html", "http_status": code}
        raw = body.read_bytes()
        return {"status": "html_fetched", "http_status": code,
                "html_sha256": hashlib.sha256(raw).hexdigest(),
                "text": raw.decode("utf-8", errors="replace")}


def _fetch(url: str, timeout: int = 10) -> dict:
    p = urllib.parse.urlsplit(url)
    if (p.scheme != "https" or p.hostname not in ALLOW or
            p.username or p.password or p.port not in (None, 443)):
        raise ValueError("Not an allowlisted HTTPS source")
    opener = urllib.request.build_opener(_StrictRedirect())
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ArvectumResearch/1.0)",
        "Accept": "text/html,application/xhtml+xml"})
    try:
        with opener.open(request, timeout=timeout) as response:
            typ = response.headers.get("Content-Type", "")
            raw = response.read(MAX_HTML_BYTES + 1)
            if len(raw) > MAX_HTML_BYTES:
                return {"status": "body_budget_exceeded", "http_status": response.status}
            if "text/html" not in typ.lower():
                return {"status": "non_html", "http_status": response.status,
                        "content_type": typ[:100]}
            text = raw.decode("utf-8", errors="replace")
            return {"status": "html_fetched", "http_status": response.status,
                    "html_sha256": hashlib.sha256(raw).hexdigest(),
                    "text": text}
    except urllib.error.HTTPError:
        # Access controls and explicit HTTP errors are never bypassed.
        raise
    except urllib.error.URLError:
        return _fetch_direct_verified_tls(url, timeout=timeout)


def audit(*, queue_file: Path, journal: Path, max_tasks: int = 5,
          retry_hours: int = 12, fetch=None,
          prior_journals: list[Path] | None = None) -> dict:
    if not 1 <= max_tasks <= 30 or not 1 <= retry_hours <= 720:
        raise ValueError("Invalid probe limits")
    fetcher = fetch or _fetch
    tasks = json.loads(queue_file.read_text(encoding="utf-8"))["tasks"]
    state = json.loads(journal.read_text(encoding="utf-8")) if journal.exists() else {
        "schema_version": "pq-etp-card-attempts/1", "attempts": []}
    # One source URL can appear under several candidate IDs and in a separate
    # native-ETP journal. A recent verified attempt must not be replayed.
    prior_attempts = list(state["attempts"])
    for other in prior_journals or []:
        if other.is_file():
            other_data = json.loads(other.read_text(encoding="utf-8"))
            if not isinstance(other_data, dict) or not isinstance(
                    other_data.get("attempts"), list):
                raise ValueError("Invalid prior ETP attempt journal")
            prior_attempts.extend(other_data["attempts"])
    now = datetime.now(UTC)
    new = []
    for task in tasks:
        if len(new) >= max_tasks:
            break
        url = task.get("mirror")
        identity = str(task.get("procedure_id") or task.get("owner") or "")
        if not isinstance(url, str) or not url or not identity:
            continue
        host = urllib.parse.urlsplit(url).hostname
        if host not in ALLOW:
            continue
        matching = [a for a in prior_attempts if a.get("url") == url]
        if matching:
            try:
                times = [datetime.fromisoformat(a["timestamp"]) for a in matching]
                if any(t.tzinfo is None for t in times):
                    raise ValueError("Naive attempt timestamp")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Invalid ETP attempt timestamp") from exc
            if any(now - t < timedelta(hours=retry_hours) for t in times):
                continue
        try:
            result = fetcher(url)
            html = result.pop("text", "")
            result["identity_mentioned"] = identity.casefold() in html.casefold()
            result["pq_term_mentioned"] = any(t in html.casefold() for t in
                                               ("укрм","компенсац","статком","конденсатор","фильтр гармоник"))
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            status = ("inaccessible" if code in (401, 403) else
                      "not_found" if code == 404 else
                      "retryable_http_error" if code in (408, 429, 500, 502, 503, 504) else
                      "http_error")
            result = {"status": status, "http_status": code, "error_type": "HTTPError"}
        except urllib.error.URLError:
            result = {"status": "retryable_network_error", "error_type": "URLError"}
        except (OSError, ValueError) as exc:
            result = {"status": "fetch_error", "error_type": type(exc).__name__}
        previous_count = sum(a["procedure_id"] == identity and a["url"] == url
                             for a in state["attempts"])
        record = {"timestamp": now.isoformat(), "procedure_id": identity, "url": url,
                  "host": host, "source_tier": "original_corporate" if host in PRIMARY else "secondary_index",
                  "retry_count": previous_count + 1,
                  "next_eligible_retry_at": (now + timedelta(hours=retry_hours)).isoformat(),
                  **result, "signed_contract_verified": False, "winner_verified": False}
        state["attempts"].append(record)
        prior_attempts.append(record)
        new.append(record)
        journal.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=journal.parent,
                                         prefix=".etp-", delete=False) as f:
            tmp = Path(f.name)
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, journal)
    return {"probes": len(new), "total_attempts": len(state["attempts"]),
            "html_fetched": sum(a["status"] == "html_fetched" for a in new),
            "results": new}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queue-file", type=Path, required=True)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--max-tasks", type=int, default=5)
    p.add_argument("--prior-journal", type=Path, action="append")
    args = p.parse_args()
    result = audit(queue_file=args.queue_file, journal=args.journal,
                   max_tasks=args.max_tasks, prior_journals=args.prior_journal)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__": main()
