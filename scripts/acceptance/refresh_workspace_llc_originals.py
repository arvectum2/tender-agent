"""Read-only five original Workspace source refresh; no private account or external action.

Use pre-existing first-party card receipts; do not silently broaden to other URLs.
Missing/changed source facts fail closed and never become an LLC permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

if __package__ in (None, "") and __file__ != "<stdin>":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.acceptance.audit_schlam_offer_original_oct17 import _Markup
from scripts.acceptance.audit_workspace_oct17_cards import extract_public_card
from src.tender_research.corporate_lead_gate import qualify_llc_response

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "roadmap"
MAX_BYTES = 400_000


def original_cases(source_dir: Path = SOURCES) -> list[dict]:
    four = json.loads(
        (source_dir / "b2b_workspace_four_original_fit_2026-10-17.json").read_text(encoding="utf-8")
    )
    schlam = json.loads(
        (source_dir / "b2b_schlam_19006_original_offer_qa_2026-10-17.json").read_text(encoding="utf-8")
    )
    cases = [{
        "id": case["id"],
        "url": case["source_url"],
        "deadline": case["original_public_deadline_date"],
        "anchors": case["original_public_evidence_literals"],
        "old_sha": case["original_html_sha256"],
    } for case in four["cases"]]
    original = schlam["original_workspace_card"]
    cases.append({
        "id": "19006", "url": original["url"],
        "deadline": original["deadline_date"],
        "anchors": original["original_literal_source_requirements"],
        "old_sha": original["original_html_sha256"],
    })
    if {x["id"] for x in cases} != {"19030", "19032", "19042", "19043", "19006"}:
        raise ValueError("unexpected original card inventory")
    for c in cases:
        p = urlsplit(c["url"])
        if (p.scheme != "https" or p.hostname != "workspace.ru"
            or p.username is not None or p.password is not None or p.port is not None
            or p.query or p.fragment or
            re.fullmatch(r"/tenders/[a-z0-9-]+-" + c["id"] + r"/", p.path) is None):
            raise ValueError("unexpected original card URL")
    return sorted(cases, key=lambda x: (x["deadline"], x["id"]))


def evaluate_original(case: dict, data: bytes, *, observed: datetime) -> dict:
    """Parse pinned original format, fail closed on changed or missing evidence."""
    result = {
        "id": case["id"],
        "source_url": case["url"],
        "source_observed_at_utc": observed.isoformat(),
        "original_html_sha256": hashlib.sha256(data).hexdigest(),
        "original_html_bytes": len(data),
        "previous_original_sha256": case["old_sha"],
        "html_changed_since_previous_receipt": hashlib.sha256(data).hexdigest() != case["old_sha"],
        "published_deadline_date": case["deadline"],
        "deadline_clock_time": "UNKNOWN",
        "source_status": "SOURCE_REVIEW_REQUIRED",
        "source_reason": "original_card_not_unambiguously_parsed",
        "mandatory_text_anchors_verified": False,
        "company_response_eligibility": "NOT_VERIFIED",
        "company_pro_or_invite_access": "NOT_VERIFIED",
        "mandatory_company_portfolio": "NOT_VERIFIED",
        "owner_go": False,
        "response_authorized": False,
        "paid_actions_or_responses": 0,
    }
    try:
        key = case["id"]
        slug = urlsplit(case["url"]).path.rstrip("/").split("/")[-1].removesuffix("-" + key)
        parsed = extract_public_card(
            data, key=key, observed=observed,
            allowed_cards={key: (slug, case["deadline"], "FIT_HIGH")},
        )
        text = _Markup()
        text.feed(data.decode("utf8", "strict"))
        missing = [
            anchor for anchor in case["anchors"]
            if " ".join(anchor.casefold().split()) not in " ".join(text.text.casefold().split())
        ]
        if missing:
            result["source_reason"] = "original_requirement_anchors_missing"
            return result
        original = {
            "source_url": case["url"],
            "organizer_type": parsed["organizer_type"],
            "platform_status": parsed["platform_status"],
            "submission_deadline": parsed["application_deadline_date"],
            "source_observed_at": observed.isoformat(),
        }
        legal = qualify_llc_response(
            original, checked_at=observed,
            source_sha256=result["original_html_sha256"], source_http_status=200,
        )
        result.update({
            "source_status": parsed["source_status_gate"],
            "source_reason": parsed["source_status_reason"],
            "platform_status_literal": parsed["platform_status"],
            "organizer_type_literal": parsed["organizer_type"],
            "mandatory_text_anchors_verified": True,
            "mandatory_text_anchors_count": len(case["anchors"]),
            "company_response_eligibility": legal.state,
            "unresolved_llc_gates": list(legal.blockers),
        })
    except (ValueError, UnicodeError) as exc:
        # Source ambiguity is not an eligible/canceled legal determination.
        result["source_reason"] = "original_source_changed_or_ambiguous"
        result["parse_error_type"] = type(exc).__name__
    return result


def collect(*, source_dir: Path = SOURCES) -> dict:
    opener = build_opener(ProxyHandler({}))
    cases = []
    for case in original_cases(source_dir):
        entry = None
        try:
            with opener.open(
                Request(case["url"], headers={"User-Agent": "ArvectumTenderAgent-SourceResearch/1.0"}),
                timeout=12,
            ) as response:
                if response.status != 200 or response.geturl() != case["url"]:
                    raise ValueError("original URL redirect or HTTP not 200")
                raw = response.read(MAX_BYTES + 1)
            observed = datetime.now(UTC)
            if not 100 <= len(raw) <= MAX_BYTES:
                raise ValueError("original source body size out of bounds")
            entry = evaluate_original(case, raw, observed=observed)
            entry["source_http_status"] = 200
        except (OSError, ValueError) as exc:
            entry = {
                "id": case["id"], "source_url": case["url"],
                "source_observed_at_utc": datetime.now(UTC).isoformat(),
                "source_status": "SOURCE_REVIEW_REQUIRED",
                "source_reason": "original_source_not_available_or_changed",
                "source_error_type": type(exc).__name__,
                "company_response_eligibility": "NOT_VERIFIED",
                "response_authorized": False, "owner_go": False,
                "paid_actions_or_responses": 0,
            }
        cases.append(entry)
    return {
        "schema_version": "workspace-first-party-llc-refresh-v1",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "source": "direct_exact_public_original_workspace_no_auth",
        "public_candidate_count": sum(x["source_status"] == "PUBLIC_CANDIDATE_ONLY" for x in cases),
        "original_card_count": len(cases),
        "confirmed_llc_response_eligibility_count": 0,
        "externally_submitted_replies_or_paid_actions": 0,
        "source_hash_change_is_not_proof_of_material_notice_change": True,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = collect()
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FIRST_PARTY_ORIGINALS", report["original_card_count"],
          "PUBLIC_CANDIDATES", report["public_candidate_count"],
          "LLC_CONFIRMED", report["confirmed_llc_response_eligibility_count"])


if __name__ == "__main__":
    main()
