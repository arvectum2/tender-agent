"""Recheck historical customer-report deadlines against first-party EIS XML dates.

Saved customer decisions cannot be treated as current legal findings.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


def _parse_deadline(value:str)->datetime:
    if not value or not isinstance(value,str):
        raise ValueError("missing source deadline")
    try:
        parsed=datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed=datetime.strptime(value,"%d.%m.%Y %H:%M:%S %z")
        except ValueError as exc:
            raise ValueError("not a grounded source date format") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("source date has no timezone")
    return parsed


def audit_saved_decisions(
    expert_cases:list[dict],
    official_notices:list[dict],
    saved_runs:Path,
)->dict:
    indexed={item["registry_number"]:item for item in official_notices}
    if len(expert_cases)!=10 or len(indexed)!=20:
        raise ValueError("incomplete original source/report review matrix")
    checks=[]
    for case in expert_cases:
        number=case["reg_number"]
        if number not in indexed:
            raise ValueError("original EIS notice missing for saved report")
        report_path=saved_runs/case["run_id"]/"output/canonical_report.json"
        if not report_path.is_file():
            raise ValueError("persisted customer report unexpectedly unavailable")
        source=report_path.read_bytes()
        report=json.loads(source)
        if str(report.get("procurement_number"))!=number:
            raise ValueError("saved model customer report linked to wrong original procurement")
        published=report.get("application_deadline")
        official=indexed[number].get("archived_submission_end")
        if official:
            matches=_parse_deadline(published)==_parse_deadline(official)
            deadline="CONSISTENT_WITH_HISTORICAL_ORIGINAL" if matches else "CONFLICTS_WITH_HISTORICAL_ORIGINAL"
        else:
            deadline="ORIGINAL_NOT_ATTESTED"
        decision=str(report.get("decision") or "")
        checks.append({
            "registry_number":number,
            "saved_report_sha256":hashlib.sha256(source).hexdigest(),
            "archived_deadline":official,
            "previous_report_deadline":published,
            "historical_deadline_relation":deadline,
            "model_claims_strong_blocker": "подтверждён жёсткий блокер" in decision.lower(),
            "human_decision_reviewed":False,
            "live_eis_revision_attested":False,
            "bid_ready":False,
        })
    return {
        "saved_reports_verified":len(checks),
        "date_conflict_count":sum(c["historical_deadline_relation"]=="CONFLICTS_WITH_HISTORICAL_ORIGINAL" for c in checks),
        "historical_matches_count":sum(c["historical_deadline_relation"]=="CONSISTENT_WITH_HISTORICAL_ORIGINAL" for c in checks),
        "unattested_strong_blocker_decisions":sum(c["model_claims_strong_blocker"] for c in checks),
        "human_business_approved":0,
        "cases":sorted(checks,key=lambda c:c["registry_number"]),
    }
