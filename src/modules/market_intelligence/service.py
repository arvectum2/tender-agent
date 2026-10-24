"""Deterministic market observations; no network calls, LLM inference, or TAM claims.

Input is a *verified, normalized* evidence snapshot produced by upstream acquisition.
Do not pass raw supplier URLs or unverified keyword hits as established demand.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit


class MarketInputError(ValueError):
    """Source snapshot does not satisfy the bounded analytics contract."""


_STAGES = {"planned", "open", "awarded", "completed", "cancelled"}
_SCOPES = {"epc", "design", "supply", "maintenance", "unknown"}
_REGIMES = {"44-fz", "223-fz", "commercial", "other"}
_ROLES = {"epc": "epc_contractor", "design": "designer", "supply": "supplier",
          "maintenance": "service_provider", "unknown": "unknown"}
_FINAL = {"awarded", "completed"}


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise MarketInputError(f"{field}: expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MarketInputError(f"{field}: invalid date") from exc


def _money(value: Any, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise MarketInputError(f"{field}: expected nonnegative decimal string")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise MarketInputError(f"{field}: invalid decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise MarketInputError(f"{field}: expected finite nonnegative amount")
    return parsed


def _identity(value: Any, field: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MarketInputError(f"{field}: expected organization mapping")
    name = str(value.get("name") or "").strip()
    inn = str(value.get("inn") or "").strip()
    if not name and not inn:
        return None
    if inn and (not inn.isdigit() or len(inn) not in (10, 12)):
        raise MarketInputError(f"{field}: invalid INN")
    return {"name": name, "inn": inn}


def _org_key(org: dict[str, str] | None) -> str:
    if not org:
        return ""
    return "inn:" + org["inn"] if org["inn"] else "name:" + org["name"].casefold()


def _evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MarketInputError("record.evidence: expected list")
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise MarketInputError("record.evidence: expected object")
        url, locator, excerpt = (str(item.get(k) or "").strip()
                                 for k in ("url", "locator", "excerpt"))
        parsed = urlsplit(url)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc
                or not locator or not excerpt):
            raise MarketInputError("evidence requires HTTP(S) URL, locator and excerpt")
        facts = item.get("facts", [])
        if not isinstance(facts, list) or any(not isinstance(f, str) for f in facts):
            raise MarketInputError("evidence.facts: expected string list")
        result.append({"url": url, "locator": locator, "excerpt": excerpt,
                       "facts": sorted(set(facts)), "source_type":
                       str(item.get("source_type") or "unspecified")})
    return result


def _normalize(raw: Any, product_ids: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MarketInputError("record must be an object")
    regime = str(raw.get("regime") or "").lower()
    stage = str(raw.get("stage") or "").lower()
    scope = str(raw.get("scope") or "unknown").lower()
    if regime not in _REGIMES or stage not in _STAGES or scope not in _SCOPES:
        raise MarketInputError("record: unsupported regime, stage or scope")
    procurement_id = str(raw.get("procurement_id") or "").strip()
    lot_id = str(raw.get("lot_id") or "1").strip()
    award_id = str(raw.get("award_id") or "").strip()
    source = str(raw.get("source") or "").strip()
    external_id = str(raw.get("external_id") or "").strip()
    if not source or not external_id or not procurement_id or not lot_id:
        raise MarketInputError("source, external_id, procurement_id and lot_id required")
    proof = _evidence(raw.get("evidence"))
    facts = {f for ev in proof for f in ev["facts"]}
    matched_ids = sorted(f.removeprefix("product:") for f in facts
                         if f.startswith("product:") and f.removeprefix("product:") in product_ids)
    unknown = {f.removeprefix("product:") for f in facts if f.startswith("product:")} - product_ids
    if unknown:
        raise MarketInputError(f"evidence references unknown products: {sorted(unknown)}")
    scope = scope if "scope" in facts else "unknown"
    parsed_value = _money(raw.get("value_rub"), "value_rub")
    parsed_component = _money(raw.get("component_value_rub"), "component_value_rub")
    price_basis = str(raw.get("price_basis") or "unknown")
    if price_basis not in {"contract", "award", "ceiling", "unknown"}:
        raise MarketInputError("unsupported price_basis")
    if f"price_basis:{price_basis}" not in facts:
        price_basis = "unknown"
    price = (parsed_value if "value" in facts and price_basis in {"contract", "award"}
             else None)
    ceiling = (parsed_value if "value" in facts and price_basis == "ceiling" else None)
    component = (parsed_component if "component_value" in facts
                 and "component_basis:contract_line" in facts else None)
    flags: list[str] = []
    if price is not None and component is not None and component > price:
        component = None
        flags.append("COMPONENT_EXCEEDS_AWARD_PRICE")
    winner = _identity(raw.get("winner"), "winner") if "winner" in facts else None
    buyer = _identity(raw.get("buyer"), "buyer") if "buyer" in facts else None
    participants = raw.get("participants", [])
    if not isinstance(participants, list):
        raise MarketInputError("participants must be a list")
    verified_participants = ([_identity(p, "participant") for p in participants]
                             if "participants" in facts else [])
    verified_participants = [p for p in verified_participants if p]
    observed = _date(raw.get("observed_on"), "observed_on")
    event = _date(raw.get("event_on"), "event_on")
    deadline = (_date(raw.get("deadline_on"), "deadline_on")
                if "deadline" in facts and raw.get("deadline_on") else None)
    return {
        "regime": regime, "procurement_id": procurement_id, "lot_id": lot_id,
        "award_id": award_id or None, "source": source, "external_id": external_id,
        "stage": stage, "scope": scope, "event_on": event.isoformat(),
        "observed_on": observed.isoformat(), "deadline_on": deadline.isoformat() if deadline else None, "project_id": str(raw.get("project_id") or "").strip(),
        "project_name": str(raw.get("project_name") or "").strip(),
        "buyer": buyer, "winner": winner, "participants": verified_participants,
        "matched_product_ids": matched_ids, "value_rub": price,
        "nmck_rub": ceiling, "price_basis": price_basis,
        "component_value_rub": component,
        "dedicated_lot": bool(raw.get("dedicated_lot") and "dedicated_lot" in facts),
        "evidence": proof, "sources": [{"source": source, "external_id": external_id}],
        "quality_flags": flags,
    }


def _key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (item["regime"], item["procurement_id"], item["lot_id"],
            item["award_id"] or "")


def _reconcile(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[_key(item)].append(item)
    result = []
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda i: (i["observed_on"], i["source"], i["external_id"]))
        # The most recently observed official state wins; contradictory claims
        # in the same observation date are quarantined, not silently averaged.
        latest = members[-1].copy()
        latest["evidence"] = []
        latest["sources"] = []
        latest["quality_flags"] = sorted({flag for m in members for flag in m["quality_flags"]})
        latest["matched_product_ids"] = []
        seen_source = set()
        seen_evidence = set()
        for row in members:
            for source in row["sources"]:
                source_key = (source["source"], source["external_id"])
                if source_key not in seen_source:
                    latest["sources"].append(source)
                    seen_source.add(source_key)
            for evidence in row["evidence"]:
                signature = (evidence["url"], evidence["locator"], evidence["excerpt"],
                             tuple(evidence["facts"]))
                if signature not in seen_evidence:
                    latest["evidence"].append(evidence)
                    seen_evidence.add(signature)
            if row["observed_on"] == latest["observed_on"]:
                latest["matched_product_ids"].extend(row["matched_product_ids"])
        latest["matched_product_ids"] = sorted(set(latest["matched_product_ids"]))
        latest_same_day = [m for m in members if m["observed_on"] == latest["observed_on"]]
        verified_bidders = {}
        for m in latest_same_day:
            for bidder in m["participants"]:
                verified_bidders[_org_key(bidder)] = bidder
        latest["participants"] = [verified_bidders[k] for k in sorted(verified_bidders)]
        for field in ("stage", "scope", "buyer", "winner", "value_rub",
                      "nmck_rub", "component_value_rub", "dedicated_lot", "project_id"):
            # Null is non-observation, not a disagreement. Proof-backed conflicting
            # facts invalidate money, winner, stage, or scope until manually resolved.
            values = {
                _org_key(m[field]) if field in ("buyer", "winner") else str(m[field])
                for m in latest_same_day if m[field] not in (None, "", "unknown")
            }
            if len(values) > 1:
                latest["quality_flags"].append("CONFLICT_" + field.upper())
                if field in ("value_rub", "nmck_rub", "component_value_rub", "winner", "buyer"):
                    latest[field] = None
                elif field == "scope":
                    latest[field] = "unknown"
                elif field == "stage":
                    latest[field] = "conflicted"
                elif field == "dedicated_lot":
                    latest[field] = False
                else:
                    latest[field] = ""
        latest["sources"].sort(key=lambda s: (s["source"], s["external_id"]))
        result.append(latest)
    return result


def _amount(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def analyze_market(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze source-bound procurement observations; never infer total market TAM."""
    if not isinstance(payload, dict):
        raise MarketInputError("payload must be an object")
    start = _date(payload.get("window_from"), "window_from")
    end = _date(payload.get("window_to"), "window_to")
    as_of = _date(payload.get("as_of"), "as_of")
    if start > end or end > as_of:
        raise MarketInputError("invalid date window or future window end")
    supplier = payload.get("supplier", {})
    if not isinstance(supplier, dict) or not str(supplier.get("name") or "").strip():
        raise MarketInputError("supplier.name required")
    products = supplier.get("products", [])
    if not isinstance(products, list) or not products:
        raise MarketInputError("supplier.products must be nonempty list")
    ids = [str(p.get("id") or "").strip() for p in products if isinstance(p, dict)]
    if len(ids) != len(products) or len(set(ids)) != len(ids) or not all(ids):
        raise MarketInputError("supplier product IDs must be unique nonempty strings")
    if not all(isinstance(p.get("name"), str) and p["name"].strip() for p in products):
        raise MarketInputError("supplier product names required")
    coverage = payload.get("coverage", [])
    if not isinstance(coverage, list):
        raise MarketInputError("coverage must be a list")
    for row in coverage:
        if not isinstance(row, dict) or row.get("status") not in (
            "not_checked", "partial", "verified_scope", "unavailable"
        ) or not row.get("source"):
            raise MarketInputError("invalid coverage entry")
    raw_records = payload.get("records", [])
    if not isinstance(raw_records, list):
        raise MarketInputError("records must be a list")
    observed = [_normalize(rec, set(ids)) for rec in raw_records]
    # As-of validity is enforced, but records outside target market window are
    # not used in the period totals.
    if any(_date(r["observed_on"], "observed_on") > as_of for r in observed):
        raise MarketInputError("observation is newer than report as_of")
    observed = [r for r in observed if start <= _date(r["event_on"], "event_on") <= end]
    reconciled = _reconcile(observed)
    # A notice shadowed by one or more contracts in its lot is no longer open.
    awarded_lots = {(r["regime"], r["procurement_id"], r["lot_id"])
                    for r in reconciled if r["award_id"] and r["stage"] in _FINAL}
    relevant = [r for r in reconciled if r["matched_product_ids"]]
    addressable = Decimal(0)
    epc_envelope = Decimal(0)
    direct_supply = Decimal(0)
    embedded_component = Decimal(0)
    total_awarded_scope = Decimal(0)
    no_priced_component = 0
    open_rows = []
    annual = defaultdict(lambda: {
        "procedures": 0, "awarded": 0, "open": 0,
        "confirmed_equipment_rub": Decimal(0),
    })
    bidders = {}
    no_participant_roster = 0
    account_index: dict[str, dict[str, Any]] = {}
    for item in relevant:
        year = annual[item["event_on"][:4]]
        year["procedures"] += 1
        if item["stage"] in _FINAL:
            year["awarded"] += 1
        if not item["participants"]:
            no_participant_roster += 1
        for bidder in item["participants"]:
            bidder_id = _org_key(bidder)
            if bidder_id not in bidders:
                bidders[bidder_id] = {"name": bidder["name"], "inn": bidder["inn"], "count": 0}
            bidders[bidder_id]["count"] += 1
        winner_award = item["stage"] in _FINAL
        priced = False
        if winner_award:
            if item["value_rub"] is not None:
                total_awarded_scope += item["value_rub"]
                if item["scope"] == "epc":
                    epc_envelope += item["value_rub"]
            if item["scope"] in ("epc", "supply", "maintenance") and item["component_value_rub"] is not None:
                embedded_component += item["component_value_rub"]
                addressable += item["component_value_rub"]
                priced = True
                year["confirmed_equipment_rub"] += item["component_value_rub"]
            elif (item["scope"] == "supply" and item["dedicated_lot"]
                  and item["value_rub"] is not None):
                direct_supply += item["value_rub"]
                year["confirmed_equipment_rub"] += item["value_rub"]
                addressable += item["value_rub"]
                priced = True
            if not priced:
                no_priced_component += 1
        is_open = (
            item["stage"] == "open"
            and item["deadline_on"] is not None
            and _date(item["deadline_on"], "deadline_on") >= as_of
            and _date(item["observed_on"], "observed_on") >= as_of - timedelta(days=7)
            and (item["regime"], item["procurement_id"], item["lot_id"])
            not in awarded_lots
        )
        if item["stage"] == "open" and not is_open:
            item["quality_flags"].append("OPEN_STATUS_UNVERIFIED_OR_STALE")
        if is_open:
            open_rows.append(item)
            year["open"] += 1
        targets = []
        if item["buyer"]:
            targets.append(("end_customer", item["buyer"]))
        if winner_award and item["winner"] and item["scope"] != "unknown":
            targets.append((_ROLES[item["scope"]], item["winner"]))
        for role, org in targets:
            key = (role, _org_key(org))
            if not key[1]:
                continue
            key_text = "|".join(key)
            if key_text not in account_index:
                account_index[key_text] = {
                    "name": org["name"], "inn": org["inn"], "role": role,
                    "procurements": set(), "projects": set(), "open_procurements": set(),
                    "products": set(), "evidence_urls": set(),
                }
            account = account_index[key_text]
            procurement_key = "/".join(_key(item))
            account["procurements"].add(procurement_key)
            if item["project_id"]:
                account["projects"].add(item["project_id"])
            if is_open:
                account["open_procurements"].add(procurement_key)
            account["products"].update(item["matched_product_ids"])
            account["evidence_urls"].update(e["url"] for e in item["evidence"])
    annual_view = {
        year: {
            "procedures": data["procedures"],
            "awarded": data["awarded"],
            "open": data["open"],
            "confirmed_equipment_rub": _amount(data["confirmed_equipment_rub"]),
        }
        for year, data in sorted(annual.items())
    }
    ranked = []
    for account in account_index.values():
        procedures = len(account["procurements"])
        opened = len(account["open_procurements"])
        projects = len(account["projects"])
        # Explainable heuristic only; not a calibrated probability of a contract.
        score = min(100, 15 + min(opened, 2) * 27 + min(procedures, 4) * 7
                    + min(projects, 3) * 4)
        route = {"end_customer": "уточнить технического заказчика и планы проектов",
                 "epc_contractor": "предложить комплектацию конкретного EPC-пакета",
                 "designer": "войти на стадию проектирования и спецификаций",
                 "supplier": "проверить канал поставки или локальное партнёрство",
                 "service_provider": "предложить модернизацию и сервисное партнёрство"}.get(account["role"], "review")
        ranked.append({
            "name": account["name"], "inn": account["inn"], "role": account["role"],
            "heuristic_priority_score": score, "procurement_count": procedures,
            "open_count": opened, "project_count": projects,
            "product_ids": sorted(account["products"]),
            "evidence_urls": sorted(account["evidence_urls"]),
            "suggested_next_step": route,
        })
    ranked.sort(key=lambda a: (-a["heuristic_priority_score"], -a["procurement_count"],
                               a["name"], a["role"]))
    view = []
    for rec in relevant:
        out = dict(rec)
        out["value_rub"] = _amount(out["value_rub"])
        out["nmck_rub"] = _amount(out["nmck_rub"])
        out["component_value_rub"] = _amount(out["component_value_rub"])
        out["is_open_opportunity"] = rec in open_rows
        out["attribution"] = (
            "confirmed_component_value" if rec["stage"] in _FINAL
            and rec["scope"] in ("epc", "supply", "maintenance")
            and rec["component_value_rub"] is not None else
            "dedicated_supply_value" if rec["stage"] in _FINAL and rec["scope"] == "supply"
            and rec["dedicated_lot"] and rec["value_rub"] is not None else
            "unpriced_or_not_awarded"
        )
        view.append(out)
    return {
        "schema_version": "market-intelligence/0.1",
        "supplier": {"name": supplier["name"], "products": products},
        "window_from": start.isoformat(), "window_to": end.isoformat(),
        "as_of": as_of.isoformat(), "coverage": coverage,
        "market_size_status": "INSUFFICIENT_COVERAGE",
        "market_size_rub": None,
        "counts": {
            "input_records": len(raw_records), "in_window_records": len(observed),
            "deduplicated_lots_awards": len(reconciled),
            "relevant_lots_awards": len(relevant), "open_opportunities": len(open_rows),
            "awarded_relevant_without_product_price": no_priced_component,
        },
        "observed_award_values_rub": {
            "confirmed_dedicated_supply": _amount(direct_supply),
            "confirmed_embedded_component": _amount(embedded_component),
            "confirmed_addressable_total": _amount(addressable),
            "relevant_full_procurement_envelope": _amount(total_awarded_scope),
            "epc_full_envelope_not_market_size": _amount(epc_envelope),
        },
        "annual_observations": annual_view,
        "observed_participants": sorted(
            bidders.values(), key=lambda x: (-x["count"], x["name"], x["inn"])
        ),
        "procedures_without_verified_participant_roster": no_participant_roster,
        "procurements": view, "accounts": ranked,
        "limitations": [
            "These are sums of explicitly evidenced observed awards, NOT a market census or TAM.",
            "Full EPC scope value is NOT attributed to component product demand.",
            "Missing protocols, private ETPs, direct commercial deals and unpriced line items are unknown, not zero.",
            "Open opportunities require a sourced deadline and status observation within seven days of report time.",
            "Design-stage contract values do not prove that equipment was purchased.",
            "Account priority is an uncalibrated deterministic heuristic, not a win probability.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Readable executive handoff, with no unsupported three-year market-size claim."""
    counts = report["counts"]
    values = report["observed_award_values_rub"]
    lines = [
        f"# Анализ рынка: {report['supplier']['name']}",
        f"Срез: {report['as_of']}; период {report['window_from']} — {report['window_to']}.",
        "**Статус оценки полного рынка: недостаточно подтверждённого охвата источников.**",
        (f"Обнаружено релевантных закупок/лотов/контрактов: {counts['relevant_lots_awards']}; "
        f"открытых: {counts['open_opportunities']}."),
        (f"Подтверждённый объём выбранных компонентных позиций в наблюдаемых "
        f"заключённых закупках: {values['confirmed_addressable_total']} ₽."),
        (f"Из них отдельные поставки: {values['confirmed_dedicated_supply']} ₽; "
        f"явно оценённые компоненты EPC/проектов: {values['confirmed_embedded_component']} ₽."),
        (f"Общая стоимость наблюдаемых EPC-контрактов, **не** стоимость рынка "
        f"оборудования: {values['epc_full_envelope_not_market_size']} ₽."),
        (f"Без подтверждённой цены продукции: "
        f"{counts['awarded_relevant_without_product_price']} завершённых закупок."),
        "",
        "## Кому выходить (эвристический приоритет, не вероятность выигрыша)",
    ]
    for a in report["accounts"][:30]:
        refs = ", ".join(a["evidence_urls"][:2])
        lines.append(f"- {a['name'] or a['inn']} ({a['role']}, оценка {a['heuristic_priority_score']}): "
                     f"{a['suggested_next_step']}. Источники: {refs}")
    lines += ["", "## Наблюдения по годам (не полный рынок)",
              "| Год | Релевантные процедуры | Состоявшиеся | Открытые на дату среза | Подтверждённая стоимость оборудования, ₽ |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for year, data in report["annual_observations"].items():
        lines.append(
            f"| {year} | {data['procedures']} | {data['awarded']} | "
            f"{data['open']} | {data['confirmed_equipment_rub']} |"
        )
    lines += ["", "## Источники и ограничения охвата"]
    for coverage in report["coverage"]:
        lines.append(f"- {coverage['source']}: {coverage['status']}; "
                     f"{coverage.get('notes') or 'охват не измерен'}")
    lines += ["", "## Подтверждённые участники процедур"]
    for bidder in report["observed_participants"][:30]:
        lines.append(f"- {bidder['name'] or bidder['inn']}: {bidder['count']} процедур.")
    lines.append(
        f"Процедур без подтверждённого списка участников: "
        f"{report['procedures_without_verified_participant_roster']}."
    )
    lines += ["", "## Потребности и документы"]
    for rec in report["procurements"][:100]:
        refs = ", ".join(f"{e['url']} ({e['locator']})" for e in rec["evidence"][:2])
        lines.append(f"- {rec['procurement_id']} / лот {rec['lot_id']} "
                     f"({rec['stage']}, {rec['scope']}): "
                     f"продукты {', '.join(rec['matched_product_ids'])}; {refs}")
    lines += ["", "## Ограничения"]
    lines += [f"- {item}" for item in report["limitations"]]
    return "\n".join(lines) + "\n"
