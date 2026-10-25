"""Read-only live TLS snapshot capture of the preregistered source pages.

Never fabricates notice IDs, ranks, labels or Tender Agent predictions.
If either page is inaccessible or opaque, report source status and stop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.modules.tender_operator_agent_demo.r4_prospective_sampling import (
    validate_sampling_intent,
)


def snapshot_preregistered_pages(intent: dict, output_root: Path) -> dict:
    validate_sampling_intent(intent)
    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError("Never overwrite preexisting source snapshots")
    output_root.mkdir(parents=True, exist_ok=True)
    pages = []
    now = datetime.now(UTC)
    if now < datetime.fromisoformat(intent["registered_at_utc"]):
        raise ValueError("Cannot capture future-registered source intent")
    for rank, url in enumerate(intent["page_order"], 1):
        host = urlparse(url).hostname
        if host != "tendigo.ru" or urlparse(url).scheme != "https":
            raise ValueError("Discovery must never contact unapproved source host")
        info = {
            "url": url, "source_page_rank": rank,
            "capture_started_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": "SOURCE_UNAVAILABLE", "http_status": None,
            "content_sha256": None, "html_file": None,
            "tls_context": "STANDARD_CA_CERTIFICATE_VERIFICATION",
        }
        try:
            request = Request(url, headers={"User-Agent": "Arvectum/1.0 source-only read-only"})
            with urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
                info["http_status"] = response.status
                if response.status != 200:
                    raise ValueError("Discovery page did not respond HTTP 200")
                final = response.geturl()
                if "html" not in (response.headers.get("Content-Type") or "").lower():
                    raise ValueError("Discovery response is not HTML")
                if final != url:
                    raise ValueError("Unexpected discovery page redirect; source identity changed")
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000 or len(raw) < 100:
                    raise ValueError("Discovery HTML is too small or too large")
                subdir = output_root / "sources"
                subdir.mkdir(parents=True, exist_ok=True)
                relpath = f"sources/page-{rank}.html"
                (output_root / relpath).write_bytes(raw)
                info["content_sha256"] = hashlib.sha256(raw).hexdigest()
                info["html_file"] = relpath
                info["status"] = "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED"
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            info["reason"] = type(exc).__name__ + ": " + str(exc)[:160]
        pages.append(info)
    return {
        "intent_sha256": intent["immutable_intent_sha256"],
        "recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "retrieval_scope": "SOURCE_ONLY_READ_ONLY",
        "pages": pages,
        "verified_source_pages": sum(
            p["status"] == "TLS_SHA_ORIGINAL_CAPTURED_NOT_YET_PARSED" for p in pages
        ),
        "candidate_numbers": [],
        "official_eis_originals_verified": 0,
        "human_gold_created": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    args = parser.parse_args()
    intent = json.loads(args.intent.read_text())
    result = snapshot_preregistered_pages(intent, args.private_output_root)
    (args.private_output_root / "capture-receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8",
    )
    print("LIVE_CAPTURED_PAGES", result["verified_source_pages"])
    print("DISCOVERY_ONLY_NO_OFFICIAL_SOURCE_CASES", result["official_eis_originals_verified"])


if __name__ == "__main__":
    main()
