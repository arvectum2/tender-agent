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


def parse_44fz_reference(value: str) -> str:
    """Extract a strict 19-digit EIS registry number; reject foreign URLs."""
    import re
    from urllib.parse import parse_qs, urlsplit

    raw = value.strip()
    if re.fullmatch(r"\d{19}", raw):
        return raw
    parts = urlsplit(raw)
    if parts.scheme != "https" or parts.hostname not in {"zakupki.gov.ru", "www.zakupki.gov.ru"}:
        raise ValueError("Требуется номер закупки или HTTPS-ссылка на zakupki.gov.ru")
    if not parts.path.startswith("/epz/order/notice/"):
        raise ValueError("Ссылка должна вести на извещение 44-ФЗ")
    number = parse_qs(parts.query).get("regNumber", [None])[0]
    if not number or not re.fullmatch(r"\d{19}", number):
        raise ValueError("В ссылке отсутствует корректный regNumber")
    return number


def preanalysis_from_public_search(reference: str, *, search=None) -> dict[str, Any]:
    """Search only the exact real 44-FZ card; never substitute demo/nearby tenders."""
    from time import perf_counter

    from src.modules.tender_operator_agent_demo.decision_core import build_decision_core

    registry_number = parse_44fz_reference(reference)
    if search is None:
        from src.modules.tender_operator_agent_demo.procurement_discovery import (
            search_public_44fz,
        )
        search = search_public_44fz
    started = perf_counter()
    response = search(query=registry_number, law="44fz", max_results=1)
    candidates = response.get("cards", []) if isinstance(response, dict) else []
    card = next((item for item in candidates if isinstance(item, dict) and item.get("reestr_number") == registry_number and item.get("law") == "44fz"), None)
    warnings = []
    model: dict[str, Any] = {"procurement_law": "44fz", "field_evidence": {}}
    if card:
        url = card.get("source_url")
        if isinstance(url, str) and url.startswith("https://zakupki.gov.ru/") and f"regNumber={registry_number}" in url:
            for field, card_field in (("procurement_title", "title"), ("application_deadline", "deadline"), ("nmck", "initial_price")):
                value = card.get(card_field)
                if value not in (None, ""):
                    model[field] = value
                    model["field_evidence"][field] = f"public_eis_card:{registry_number}/{card_field}"
        else:
            warnings.append("Некорректный URL первоисточника: сведения карточки не считаются подтверждёнными")
    else:
        warnings.append("Подтверждённая карточка с точным номером закупки не найдена")
    core = build_decision_core(model)
    if card and model["field_evidence"]:
        for fact in core["facts"].values():
            for evidence in fact.get("evidence", []):
                evidence["document"] = "Карточка поиска ЕИС (не документация закупки)"
                evidence["locator"] = card["source_url"]
    result = fast_cited_preanalysis(core, registry_number=registry_number)
    result["source_status"] = response.get("outcome") if isinstance(response, dict) else "source_error"
    result["latency_seconds"] = round(perf_counter() - started, 3)
    result["limitations"] = ["Требования документации, лицензии, обеспечение и условия контракта требуют анализа оригинальных документов.", *warnings]
    result["status"] = "NEEDS_REVIEW"  # A public card never establishes full bid readiness.
    return result
