"""Bounded read-only pre-analysis projection of the existing Decision Core.

This module intentionally does not extract, infer or re-score procurement data.
It only renders facts already supported by canonical source evidence.
"""
from __future__ import annotations

from typing import Any


def _citations(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [
        {key: item.get(key) for key in ("source_ref", "document", "locator", "excerpt") if item.get(key) is not None}
        for item in values[:8]
        if isinstance(item, dict) and item.get("source_ref") and item.get("document") and item.get("locator")
    ]


def fast_cited_preanalysis(core: dict[str, Any] | None, *, registry_number: str | None = None) -> dict[str, Any]:
    """Conservatively project canonical facts; never authorize commercial decisions."""
    core = core if isinstance(core, dict) else {}
    facts = core.get("facts") if isinstance(core.get("facts"), dict) else {}
    def fact(name: str) -> dict[str, Any]:
        item = facts.get(name) if isinstance(facts.get(name), dict) else {}
        citations = _citations(item.get("evidence"))
        known = item.get("status") == "KNOWN" and item.get("value") not in (None, "") and bool(citations)
        return {"status": "KNOWN" if known else "UNKNOWN", "value": item.get("value") if known else None, "citations": citations if known else []}

    def rows(name: str, limit: int) -> list[dict[str, Any]]:
        values = core.get(name)
        if not isinstance(values, list):
            return []
        result = []
        for item in values[:limit]:
            if not isinstance(item, dict):
                continue
            citations = _citations(item.get("evidence"))
            result.append({"code": item.get("code"), "summary": item.get("summary") or item.get("label"), "status": item.get("status") or ("EVIDENCED" if citations else "UNKNOWN"), "citations": citations, "evidence_status": "KNOWN" if citations else "UNKNOWN"})
        return result

    regime = core.get("procurement_regime")
    supported = regime == "44fz"
    unknowns = rows("unknowns", 12)
    if not supported:
        unknowns.insert(0, {"code": "UNSUPPORTED_OR_UNVERIFIED_REGIME", "summary": "44-ФЗ не подтверждён; pre-analysis требует проверки режима закупки.", "status": "UNKNOWN", "citations": [], "evidence_status": "UNKNOWN"})
    readiness = rows("readiness", 12)
    return {
        "contract_version": "fast-cited-preanalysis-v1",
        "registry_number": registry_number,
        "status": "READY_FOR_HUMAN_REVIEW" if supported else "NEEDS_REVIEW",
        "subject": fact("procurement_title"),
        "application_deadline": fact("application_deadline"),
        "initial_price": fact("nmck"),
        "essential_requirements": readiness,
        "blockers": rows("blockers", 12),
        "unknowns": unknowns,
        "fit_signals": [{"code": r["code"], "status": r["status"], "citations": r["citations"]} for r in readiness if r["evidence_status"] == "KNOWN"],
        "decision": "HUMAN_REVIEW_REQUIRED",
        "human_control_required": True,
        "external_action_allowed": False,
    }
