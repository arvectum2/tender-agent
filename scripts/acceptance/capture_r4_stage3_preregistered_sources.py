"""Capture only the immutable cross-vendor stage3 discovery HTML without labels.

The original HTML must be hashed and stored BEFORE any tender IDs are parsed.
This tool does not know or choose procurement numbers; it cannot run the SUT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.modules.benchmark_pipeline.contract import canonical_sha256

SOURCE_URLS = (
    "https://synapsenet.ru/search/populyarnie-zaprosi/razrabotka-programmnogo-obespecheniya",
    "https://mos-tenders.ru/aukcioni-goszakupki-konkursi/tendery-programmnogo-obespecheniya",
)


def validate_stage3_plan(plan: dict) -> None:
    if canonical_sha256({k: v for k, v in plan.items() if k != "immutable_intent_sha256"}) != plan.get(
        "immutable_intent_sha256"
    ):
        raise ValueError("Immutable cross-vendor source selection was tampered with")
    if plan.get("source_page_order") != list(SOURCE_URLS) or plan.get("target_new_cases") != 8:
        raise ValueError("Invalid predeclared vendor order/quota")
    at = datetime.fromisoformat(plan["registered_at_utc"])
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Invalid preregistration time")
    if plan.get("sut_inference_authorized") is not False or plan.get("gold_labels_authorized") is not False:
        raise ValueError("Blind prospective plan cannot authorize gold or model output")


def capture_stage3_sources(plan: dict, original_root: Path) -> dict:
    validate_stage3_plan(plan)
    if original_root.exists() and any(original_root.iterdir()):
        raise ValueError("Original source capture must never overwrite prior evidence")
    original_root.mkdir(parents=True, exist_ok=True)
    statuses = []
    for position, url in enumerate(SOURCE_URLS, 1):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "synapsenet.ru", "mos-tenders.ru",
        }:
            raise ValueError("Unapproved discovery source")
        rec = {
            "url": url,
            "source_rank": position,
            "started_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "status": "SOURCE_UNAVAILABLE",
            "body_sha256": None,
            "body_relative_path": None,
        }
        try:
            request = Request(url, headers={"User-Agent": "Arvectum/1.0 read-only-prospective-source"})
            with urlopen(request, context=ssl.create_default_context(), timeout=18) as response:
                if response.status != 200 or response.geturl() != url:
                    raise ValueError("Unpinned HTTP final response")
                if "html" not in (response.headers.get("Content-Type") or "").lower():
                    raise ValueError("No first-party HTML content")
                data = response.read(8_000_001)
                if len(data) < 100 or len(data) > 8_000_000:
                    raise ValueError("Source HTML outside bounded size")
                rel = f"source-{position}.html"
                (original_root / rel).write_bytes(data)
                rec["body_sha256"] = hashlib.sha256(data).hexdigest()
                rec["body_relative_path"] = rel
                rec["status"] = "RAW_FIRST_PARTY_TLS_HTML_SHA_LOCKED_NOT_PARSED"
        except (HTTPError, URLError, ValueError, TimeoutError, OSError) as exc:
            rec["failure_type"] = type(exc).__name__
        statuses.append(rec)
    receipt = {
        "stage3_preregistered_intent_sha256": plan["immutable_intent_sha256"],
        "capture_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_count": len(statuses),
        "successful_original_html": sum(s["status"].startswith("RAW_") for s in statuses),
        "source_capture_status": statuses,
        "model_predictions_seen": False,
        "legal_gold_labels_seen": False,
        "official_eis_cases_verified": 0,
    }
    path = original_root / "source-only-capture-receipt-private.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--immutable-intent", type=Path, required=True)
    parser.add_argument("--private-source-output", type=Path, required=True)
    args = parser.parse_args()
    result = capture_stage3_sources(
        json.loads(args.immutable_intent.read_text()),
        args.private_source_output,
    )
    for page in result["source_capture_status"]:
        print("SOURCE_ONLY_STAGE3_TLS",page["source_rank"],page["status"],
              page.get("failure_type","NONE"))
    print("CAPTURED_VERIFIED_SOURCES",result["successful_original_html"],"OF",len(SOURCE_URLS))


if __name__ == "__main__":
    main()
