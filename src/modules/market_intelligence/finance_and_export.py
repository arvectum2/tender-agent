"""MI-004: evidence-reviewed contract ledger and safe read-only client preview.

National market value is never inferred from selected tenders, EPC envelopes,
or hypothetical supplier chain purchases. Monetary values are CONTRACTED,
not necessarily delivered/paid/revenue.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class FinanceEvidenceError(ValueError):
    """Unsafe or invalid legal/financial evidence."""


RELEVANT_STAGES = {"epc", "supply", "design", "maintenance"}
TIERS = {"end_buyer", "epc_prime", "subcontract"}
PRICE_TYPES = {"contract_total", "equipment_line", "ceiling"}
STATUSES = {"awarded", "completed", "open", "unknown", "cancelled"}
PRIMARY_TYPES = {"signed_contract", "official_contract_registry", "official_protocol"}
CRITICAL_FIELDS = {"project_id", "contract_id", "notice_id", "lot_id"}


def _money(value: Any, context: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise FinanceEvidenceError(f"{context}: decimal string required")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise FinanceEvidenceError(f"{context}: invalid monetary value") from exc
    if not parsed.is_finite() or parsed < 0 or parsed >= Decimal("1e16"):
        raise FinanceEvidenceError(f"{context}: amount must be finite, nonnegative and bounded")
    return parsed


def _date(value: Any, context: str) -> str:
    try:
        if not isinstance(value, str):
            raise TypeError
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise FinanceEvidenceError(f"{context}: YYYY-MM-DD required") from exc


def _primary_proof(row: dict[str, Any]) -> bool:
    ev = row.get("evidence") or {}
    if not isinstance(ev, dict):
        return False
    link = urlsplit(str(ev.get("url") or ""))
    return bool(
        link.scheme == "https" and link.hostname
        and link.username is None and link.password is None
        and ev.get("source_type") in PRIMARY_TYPES
        and ev.get("review_state") == "approved"
        and str(ev.get("reviewer") or "").strip()
        and str(ev.get("locator") or "").strip()
        and str(ev.get("excerpt") or "").strip()
        and re.fullmatch(r"[0-9a-fA-F]{64}", str(ev.get("sha256") or ""))
    )


def _normalize(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise FinanceEvidenceError("contract observation must be a mapping")
    if any(not str(row.get(key) or "").strip() for key in CRITICAL_FIELDS):
        raise FinanceEvidenceError("missing stable procurement/project/contract identity")
    tier, scope, price_kind, stage = (
        row.get("tier"), row.get("scope"), row.get("price_type"), row.get("status")
    )
    if (
        tier not in TIERS or scope not in RELEVANT_STAGES
        or price_kind not in PRICE_TYPES or stage not in STATUSES
    ):
        raise FinanceEvidenceError("unrecognized tier, scope, price kind or status")
    if price_kind == "equipment_line" and not str(row.get("line_id") or "").strip():
        raise FinanceEvidenceError("priced equipment requires line_id")
    amount = _money(row.get("amount_rub"), "amount_rub")
    revision = _date(row.get("revision_on"), "revision_on")
    publication = _date(row.get("as_of"), "as_of")
    if revision > publication:
        raise FinanceEvidenceError("future source revision")
    if not _primary_proof(row):
        raise FinanceEvidenceError("price lacks approved primary contract/registry/protocol")
    ev = row["evidence"]
    if stage in {"awarded", "completed"} and price_kind != "ceiling" and ev["source_type"] == "official_protocol":
        # An official protocol is an award event, not proof of a signed contract
        # or completed payment. For contracted value require actual contract proof.
        raise FinanceEvidenceError("awarded contract price requires contract/registry proof")
    return {
        "project_id": str(row["project_id"]), "notice_id": str(row["notice_id"]),
        "lot_id": str(row["lot_id"]), "contract_id": str(row["contract_id"]),
        "revision_on": revision, "as_of": publication,
        "tier": tier, "scope": scope, "price_type": price_kind,
        "status": stage, "line_id": str(row.get("line_id") or ""),
        "equipment_family": str(row.get("equipment_family") or ""),
        "dedicated_equipment_lot": bool(row.get("dedicated_equipment_lot", False)),
        "amount_rub": amount, "evidence": ev,
        "chain_id": str(row.get("chain_id") or ""),
    }


def _identity(row: dict[str, Any]) -> tuple[str, ...]:
    """All mirror observations of an identical legal price fact share this ID."""
    return (
        row["project_id"], row["notice_id"], row["lot_id"],
        row["contract_id"], row["tier"], row["scope"],
        row["price_type"], row["line_id"],
    )


def _rub(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def audit_project_finance(
    observations: list[dict[str, Any]], *,
    as_of: str, source_coverage_certified: bool = False,
) -> dict[str, Any]:
    """Keep verified contracting amounts distinct by project and supply-chain tier.

    Two distinct end-buyer contract IDs for the same project are not merged
    without a verified supersession relation. Flags mark potential duplication.
    """
    snapshot = _date(as_of, "as_of")
    if not isinstance(observations, list):
        raise FinanceEvidenceError("observations must be list")
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        fact = _normalize(row)
        if fact["as_of"] > snapshot:
            raise FinanceEvidenceError("source observed after report snapshot")
        groups[_identity(fact)].append(fact)
    verified = []
    quarantined = []
    for key in sorted(groups):
        versions = groups[key]
        latest_revision = max(row["revision_on"] for row in versions)
        latest = [x for x in versions if x["revision_on"] == latest_revision]
        amounts = {x["amount_rub"] for x in latest}
        status_values = {x["status"] for x in latest}
        families = {x["equipment_family"] for x in latest}
        if len(amounts) != 1 or len(status_values) != 1 or len(families) != 1:
            quarantined.append({
                "fact_identity": key,
                "reason": "conflicting_same_revision_primary_sources",
                "source_urls": sorted({r["evidence"]["url"] for r in latest}),
            })
            continue
        row = dict(latest[0])
        row["evidence_count"] = len(latest)
        row["provenance_urls"] = sorted({r["evidence"]["url"] for r in latest})
        verified.append(row)
    project_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in verified:
        project_rows[fact["project_id"]].append(fact)
    projects = []
    cross_contract_warnings = []
    for project_id, facts in sorted(project_rows.items()):
        end_buyer = [r for r in facts if r["tier"] == "end_buyer"
                     and r["status"] in {"awarded", "completed"}]
        contracts: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in end_buyer:
            contracts[row["contract_id"]].append(row)
        awarded_component = Decimal(0)
        component_facts_count = 0
        family_contract_components: dict[str, dict[str, Decimal]] = defaultdict(dict)
        whole_epc = Decimal(0)
        epc_facts_count = 0
        design = Decimal(0)
        design_facts_count = 0
        service = Decimal(0)
        service_facts_count = 0
        ceiling = Decimal(0)
        ceiling_count = 0
        subcontract = Decimal(0)
        sub_count = 0
        reviewed_requirements: dict[str, set[str]] = defaultdict(set)
        for row in facts:
            if row["tier"] == "end_buyer" and row["price_type"] == "ceiling":
                ceiling += row["amount_rub"]
                ceiling_count += 1
            if row["tier"] != "end_buyer" and row["status"] in {"awarded", "completed"}:
                # Visible supply-chain monetary flow, NOT additive end-user market.
                subcontract += row["amount_rub"]
                sub_count += 1
            if (
                row["tier"] == "end_buyer"
                and row["status"] in {"awarded", "completed"}
                and row["equipment_family"]
                and row["price_type"] in {"equipment_line", "contract_total"}
            ):
                reviewed_requirements[row["equipment_family"]].add(row["contract_id"])
        for contract_id, rows in contracts.items():
            lines = [r for r in rows if r["price_type"] == "equipment_line"]
            totals = [r for r in rows if r["price_type"] == "contract_total"]
            invalid_component_lines = bool(
                lines and totals
                and sum((r["amount_rub"] for r in lines), Decimal(0)) >
                sum((r["amount_rub"] for r in totals), Decimal(0))
            )
            if invalid_component_lines:
                quarantined.append({
                    "fact_identity": (project_id, contract_id),
                    "reason": "equipment_lines_exceed_contract_total",
                    "source_urls": sorted({r["evidence"]["url"] for r in rows}),
                })
                # Do not count contradictory priced equipment.
                lines = []
            if lines:
                for row in lines:
                    if row["scope"] in {"supply", "epc"} and row["equipment_family"]:
                        awarded_component += row["amount_rub"]
                        component_facts_count += 1
                        by_contract = family_contract_components[row["equipment_family"]]
                        by_contract[contract_id] = (
                            by_contract.get(contract_id, Decimal(0)) + row["amount_rub"]
                        )
            elif (
                not invalid_component_lines and len(totals) == 1
                and totals[0]["scope"] == "supply"
                and totals[0]["dedicated_equipment_lot"]
                and totals[0]["equipment_family"]
            ):
                awarded_component += totals[0]["amount_rub"]
                component_facts_count += 1
                by_contract = family_contract_components[totals[0]["equipment_family"]]
                by_contract[contract_id] = (
                    by_contract.get(contract_id, Decimal(0)) + totals[0]["amount_rub"]
                )
            for row in totals:
                if row["scope"] == "epc":
                    whole_epc += row["amount_rub"]
                    epc_facts_count += 1
                elif row["scope"] == "design":
                    design += row["amount_rub"]
                    design_facts_count += 1
                elif row["scope"] == "maintenance":
                    service += row["amount_rub"]
                    service_facts_count += 1
        conservative_dedup_applied = False
        for family, contracts_seen in reviewed_requirements.items():
            if len(contracts_seen) > 1:
                values = family_contract_components.get(family, {})
                if len(values) > 1:
                    # EPC and separately procured supply can describe the same
                    # equipment. Retain a conservative maximum per family until
                    # asset/BoM-level non-overlap has been reviewed.
                    awarded_component -= sum(values.values(), Decimal(0)) - max(values.values())
                    conservative_dedup_applied = True
                cross_contract_warnings.append({
                    "project_id": project_id, "family": family,
                    "contracts": sorted(contracts_seen),
                    "reason": "same_project_family_multiple_end_buyer_contracts_requires_lifecycle_review",
                    "conservative_max_contract_applied": bool(len(values) > 1),
                })
        projects.append({
            "project_id": project_id,
            "contracted_equipment_rub": _rub(awarded_component) if component_facts_count else None,
            "contracted_equipment_facts": component_facts_count,
            "conservative_project_family_dedup": conservative_dedup_applied,
            "full_epc_contract_envelope_rub": _rub(whole_epc) if epc_facts_count else None,
            "design_contract_rub": _rub(design) if design_facts_count else None,
            "service_contract_rub": _rub(service) if service_facts_count else None,
            "subcontract_chain_value_rub_not_additive": _rub(subcontract) if sub_count else None,
            "published_ceiling_rub_not_awarded": _rub(ceiling) if ceiling_count else None,
        })
    observed_equipment_total = sum(
        (Decimal(p["contracted_equipment_rub"]) for p in projects
         if p["contracted_equipment_rub"] is not None), Decimal(0)
    )
    observed_components = sum(p["contracted_equipment_facts"] for p in projects)
    return {
        "schema_version": "mi004-project-finance/0.1",
        "as_of": snapshot,
        "verified_unique_price_facts": len(verified),
        "source_duplicates_removed": len(observations) - len(groups),
        "quarantined_price_facts": quarantined,
        "cross_contract_lifecycle_review": cross_contract_warnings,
        "project_finance": projects,
        "observed_confirmed_contracted_equipment_rub": (
            _rub(observed_equipment_total) if observed_components else None
        ),
        "national_tam_rub": None,
        "national_sam_rub": None,
        "national_som_rub": None,
        "source_coverage_certified": source_coverage_certified,
        "national_market_state": "INSUFFICIENT_COVERAGE_AND_PRIVATE_SPEND",
        "money_definition": "contracted, not payment/executed revenue",
        "nonadditive": [
            "full EPC total is never added to confirmed equipment line value",
            "subcontract chain volume is never added to end buyer equipment procurement",
            "PIР/design and maintenance contracts are not new equipment hardware CAPEX",
            "NMCK/ceiling is not awarded or paid spend",
            "source mirrors and later revisions are not additional contracts",
        ],
    }


def _safe_cell(value: Any) -> str:
    """Protect Excel-family software from formula execution on imported CSV."""
    text = str(value if value is not None else "").replace("\x00", "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text[:1] in {"\t", "\r", "\n"}:
        return "'" + text
    return text


def export_account_csv(report: dict[str, Any]) -> str:
    """Portable CRM precursor, not a list of current active tenders."""
    f = io.StringIO(newline="")
    writer = csv.writer(f, lineterminator="\n")
    writer.writerow(["priority_hypothesis", "buyer_name_reported",
                     "procedure_count_in_sample", "work_packages",
                     "next_steps", "public_source_urls", "state"])
    for row in report.get("account_playbook_unreviewed", []):
        writer.writerow([
            _safe_cell(row.get("initial_priority_hypothesis")),
            _safe_cell(row.get("buyer_name_reported")),
            str(int(row.get("observed_procedures") or 0)),
            _safe_cell("; ".join(row.get("work_packages") or [])),
            _safe_cell("; ".join(row.get("proposed_actions") or [])),
            _safe_cell("; ".join(row.get("source_urls") or [])),
            "qualification_needed_not_outreach",
        ])
    return "\ufeff" + f.getvalue()


def export_customer_html(report: dict[str, Any]) -> str:
    """Static sanitized internal customer preview. NO authenticated web portal."""
    esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
    accounts = report.get("account_playbook_unreviewed", [])
    rows = []
    for row in accounts:
        links = []
        for url in row.get("source_urls", []):
            parts = urlsplit(str(url))
            if parts.scheme != "https" or not parts.hostname or parts.username:
                continue
            safe_url = esc(url)
            links.append(f'<a href="{safe_url}" rel="noreferrer noopener" target="_blank">Источник</a>')
        action = "; ".join(row.get("proposed_actions", []))
        rows.append(
            "<tr><td>"+esc(row.get("initial_priority_hypothesis"))+"</td>"
            "<td>"+esc(row.get("buyer_name_reported"))+"</td>"
            "<td>"+esc(row.get("observed_procedures"))+"</td>"
            "<td>"+esc("; ".join(row.get("product_families", [])))+"</td>"
            "<td>"+esc(action)+"</td><td>"+", ".join(links)+"</td></tr>"
        )
    caveats = "".join("<li>"+esc(x)+"</li>" for x in report.get("critical_caveats", []))
    metrics = [
        ("Проверенных примеров", report.get("labelled_lead_count")),
        ("Покупатели в выборке", len(accounts)),
        ("Месяцев-источников", report.get("coverage", {}).get("source_month_slots")),
        ("Месяцев с проверенной полнотой", report.get("coverage", {}).get("verified_complete_slots")),
    ]
    metric_html = "".join(
        f'<div class="metric"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>'
        for label, value in metrics
    )
    css = (
        "body{margin:0;background:#f6f7fa;font-family:system-ui,sans-serif;color:#18232b;}"
        "main{max-width:1250px;margin:auto;padding:44px 28px 90px;}"
        "header{background:#20262f;color:white;padding:24px 30px;border-radius:12px;}"
        "h1{font-size:28px;margin:0 0 12px;}h2{font-size:21px;margin:36px 0 14px;}"
        ".sub{color:#b8c3c8;font-size:14px;}.metrics{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px;}"
        ".metric{background:#fff;padding:18px;border-radius:10px;flex:1;min-width:150px;border:1px solid #e6e9eb;}"
        ".metric strong{font-size:24px;display:block;color:#20262f;}.metric span{display:block;font-size:13px;color:#59636e;}"
        "table{border-collapse:collapse;width:100%;background:#fff;font-size:13px;}"
        "th,td{border-bottom:1px solid #e0e3e6;padding:12px 10px;text-align:left;vertical-align:top;}"
        "th{background:#eaedf0;font-weight:700;}a{color:#106e75;text-decoration:underline;}"
        ".warning{border-left:3px solid #e68233;background:#fff;padding:14px 18px;line-height:1.6;}"
        "footer{font-size:12px;color:#5f6971;margin-top:40px;}"
    )
    period = report.get("window") or ["unknown", "unknown"]
    period_s = f"{esc(period[0])} — {esc(period[1])}" if len(period) == 2 else "не определён"
    return (
        "<!doctype html><html lang='ru'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; "
        "img-src data:;\">"
        "<title>Power Quality — Market Intelligence (пилот)</title><style>"
        +css+"</style></head><body><main>"
        "<header><h1>POWER QUALITY · MARKET INTELLIGENCE</h1>"
        "<div class='sub'>Пилотное исследование | "+period_s+"</div>"
        "<p>Арвектум · анализ спроса на УКРМ, СТАТКОМ и фильтры гармоник</p></header>"
        "<section class='metrics'>"+metric_html+"</section>"
        "<h2>Заказчики и гипотезы выхода</h2>"
        "<div class='warning'>Это целевая выборка публично найденных процедур, а не весь рынок РФ. "
        "Приоритет — гипотеза для проверки. Победители, объёмы оборудования и действующие открытые "
        "закупки не подтверждены первичными протоколами. НМЦК и общий EPC-бюджет не равны обороту PQ.</div>"
        "<div style='overflow-x:auto;margin-top:22px'><table><thead><tr>"
        "<th>Приоритет</th><th>Организация</th><th>Процедур</th><th>Номенклатура</th>"
        "<th>Рекомендуемые действия</th><th>Доказательства</th>"
        "</tr></thead><tbody>"+ "".join(rows)+"</tbody></table></div>"
        "<h2>Границы доказательной базы</h2><ul>"+caveats+"</ul>"
        "<footer>Это статический предварительный документ, не авторизованный клиентский кабинет. "
        "Не использовать как подтверждение национального объёма рынка или наличия действующей закупки."
        "</footer></main></body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MI004 safe static customer preview")
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--html-out", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, required=True)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.evaluation, args.html_out, args.csv_out)}) != 3:
        parser.error("input and outputs must be separate files")
    report = json.loads(args.evaluation.read_text(encoding="utf-8"))
    if report.get("schema_version") != "mi003-power-quality-evaluation/0.1":
        parser.error("unsupported MI003 evaluation schema")
    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(export_customer_html(report), encoding="utf-8")
    args.csv_out.write_text(export_account_csv(report), encoding="utf-8")


if __name__ == "__main__":
    main()
