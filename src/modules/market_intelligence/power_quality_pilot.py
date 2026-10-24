"""Evidence inventory for the Power Quality pilot, not a Russian market census.

Consumes hand-verified public source cards and a versioned category ontology.
The MI-001 analyzer is used in fail-closed mode: a tender without a verified
contract and item line price cannot contribute to achieved equipment revenue.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from src.modules.market_intelligence.service import analyze_market


class PilotEvidenceError(ValueError):
    """Malformed or unsafe/ungrounded research seed."""


DATE_BASES = {
    "published", "receiving_from", "published_secondary",
    "reported_deadline_NOT_publication",
}
STATUSES = {
    "source_reports_closed", "no_bids_reported", "third_party_reports_contract",
    "unknown",
}
SOURCE_TIERS = {"primary_platform", "third_party"}
ALLOWED_SCOPES = {"supply", "design", "epc", "maintenance"}
VALID_MONEY_TYPES = {
    None, "initial_price", "nmck", "zero_placeholder",
    "third_party_final_total_unverified",
}


def _as_date(value: Any, field: str) -> date:
    try:
        if not isinstance(value, str):
            raise TypeError
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise PilotEvidenceError(f"{field}: must be YYYY-MM-DD") from exc


def _check_positive_int_or_none(value: Any, field: str) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 1
    ):
        raise PilotEvidenceError(f"{field}: positive integer or null required")


def _checked_source(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PilotEvidenceError("evidence must be a mapping")
    url = value.get("url")
    tier = value.get("source_tier")
    if (
        not isinstance(url, str)
        or urlparse(url).scheme != "https"
        or not urlparse(url).hostname
    ):
        raise PilotEvidenceError("source must be absolute HTTPS URL")
    if tier not in SOURCE_TIERS:
        raise PilotEvidenceError("source_tier must be primary_platform or third_party")
    if not str(value.get("locator") or "").strip() or not str(value.get("excerpt") or "").strip():
        raise PilotEvidenceError("source locator and excerpt are required")
    return value


def _records(payload: dict[str, Any], ontology: dict[str, Any]) -> list[dict[str, Any]]:
    families = {item["id"] for item in ontology.get("families", [])}
    if not families:
        raise PilotEvidenceError("empty ontology")
    start = _as_date(payload.get("window_from"), "window_from")
    end = _as_date(payload.get("window_to"), "window_to")
    as_of = _as_date(payload.get("as_of"), "as_of")
    if not (start <= end <= as_of):
        raise PilotEvidenceError("invalid research window")
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise PilotEvidenceError("records must be list")
    result = []
    ids = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise PilotEvidenceError(f"records[{index}]: mapping required")
        id_ = raw.get("id")
        identity = raw.get("canonical_id")
        if not isinstance(id_, str) or not id_:
            raise PilotEvidenceError("record id required")
        if id_ in ids:
            raise PilotEvidenceError(f"duplicate seed record: {id_}")
        ids[id_] = index
        if not isinstance(identity, str) or identity.count(":") < 2:
            raise PilotEvidenceError("canonical_id must contain regime and lot identity")
        published = _as_date(raw.get("publication_date"), "publication_date")
        if not (start <= published <= end):
            raise PilotEvidenceError(f"{id_}: date outside reporting window")
        if raw.get("date_basis") not in DATE_BASES:
            raise PilotEvidenceError(f"{id_}: unsupported date basis")
        if raw.get("family") not in families or raw.get("scope") not in ALLOWED_SCOPES:
            raise PilotEvidenceError(f"{id_}: unrecognized category or role scope")
        if raw.get("status") not in STATUSES:
            raise PilotEvidenceError(f"{id_}: unsupported status")
        if raw.get("reported_price_kind") not in VALID_MONEY_TYPES:
            raise PilotEvidenceError(f"{id_}: invalid price basis")
        _check_positive_int_or_none(raw.get("quantity"), f"{id_}.quantity")
        proof = raw.get("evidence")
        if not isinstance(proof, list) or not proof:
            raise PilotEvidenceError(f"{id_}: evidence required")
        for ev in proof:
            _checked_source(ev)
        if raw.get("winner") is not None or raw.get("award_id"):
            raise PilotEvidenceError(f"{id_}: unverified winner/award forbidden in candidate seed")
        if raw.get("nmck_rub") is not None and raw.get("reported_price_kind") not in (
            "initial_price", "nmck"
        ):
            raise PilotEvidenceError(f"{id_}: НМЦК cannot masquerade as contract price")
        if raw.get("reported_total_rub") is not None and raw.get("reported_price_kind") != "third_party_final_total_unverified":
            raise PilotEvidenceError(f"{id_}: unverified gross must be explicitly flagged")
        result.append(raw)
    return result


def _as_mi001(payload: dict[str, Any], records: list[dict[str, Any]],
              ontology: dict[str, Any]) -> dict[str, Any]:
    # Stage unknown is deliberate for aggregator "closed" and "contract" claims.
    # "No bids" is also only reported, not a verified cancellation.
    normalized = []
    for row in records:
        try:
            regime, number, lot = row["canonical_id"].split(":", 2)
        except ValueError as exc:
            raise PilotEvidenceError("malformed canonical_id") from exc
        if regime.replace("-", "") != row["procurement_regime"].replace("-", ""):
            raise PilotEvidenceError(f"{row['id']}: conflicting regime")
        evidence = []
        for ev in row["evidence"]:
            facts = [f"product:{row['family']}", "scope"]
            org = row.get("customer")
            if isinstance(org, dict) and org.get("name") and "Не раскрыт" not in org["name"]:
                facts.append("buyer")
            if row.get("nmck_rub") is not None:
                facts.extend(["value", "price_basis:ceiling"])
            evidence.append({
                "url": ev["url"], "locator": ev["locator"],
                "excerpt": ev["excerpt"], "facts": facts,
                "source_type": ev["source_tier"],
            })
        customer = row.get("customer") or {}
        normalized.append({
            "regime": row["procurement_regime"], "procurement_id": number, "lot_id": lot,
            "award_id": None, "source": row["platform"],
            "external_id": row["id"], "stage": "unknown",
            "scope": row["scope"], "event_on": row["publication_date"],
            "observed_on": payload["as_of"], "project_id": "",
            "project_name": row.get("project") or "",
            "buyer": {"name": customer.get("name") or "",
                      "inn": customer.get("inn") or ""},
            "winner": None, "participants": [], "price_basis": "ceiling",
            "value_rub": row.get("nmck_rub"),
            "component_value_rub": None, "dedicated_lot": False,
            "evidence": evidence,
        })
    return {
        "supplier": {
            "name": "Power Quality: рынок номенклатуры (не конкретного поставщика)",
            "products": [
                {"id": item["id"], "name": item["label"],
                 "synonyms": item.get("positive", [])}
                for item in ontology["families"]
            ],
        },
        "window_from": payload["window_from"], "window_to": payload["window_to"],
        "as_of": payload["as_of"],
        "coverage": [
            {"source": "EIS 44-FZ", "status": "unavailable",
             "notes": "Live public search probe yielded HTTP 434, no exhaustive backfill"},
            {"source": "EIS 223-FZ", "status": "unavailable",
             "notes": "Live public search probe yielded HTTP 434, no exhaustive backfill"},
            {"source": "Commercial ETP primary pages", "status": "partial",
             "notes": "Only individually identified examples, no full platform feed"},
            {"source": "Public aggregator cards", "status": "partial",
             "notes": "Biased non-random secondary search results, not full historical universe"},
            {"source": "Contracts/protocols", "status": "not_checked",
             "notes": "Winner and contract registry documents not independently reconciled"},
        ],
        "records": normalized,
    }


def analyze_pilot(
    seed: dict[str, Any], ontology: dict[str, Any],
    access_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = _records(seed, ontology)
    # Validate *before* grouping; canonical identity represents real procedure ID
    # only when verifiable. Different publication dates do not imply same award.
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[row["canonical_id"]].append(row)
    canonical = []
    for identity, mirrors in sorted(groups.items()):
        if len(mirrors) > 1:
            # A true mirror has to agree on category, buyer and event basis.
            signatures = {
                (r["family"], str((r.get("customer") or {}).get("inn") or "").strip(),
                 r["publication_date"], r["scope"])
                for r in mirrors
            }
            if len(signatures) > 1:
                raise PilotEvidenceError(f"canonical identity conflict: {identity}")
        row = dict(mirrors[0])
        seen_links = set()
        proof = []
        for mirror in mirrors:
            for ev in mirror["evidence"]:
                if ev["url"] not in seen_links:
                    proof.append(ev)
                    seen_links.add(ev["url"])
        row["evidence"] = proof
        row["mirror_record_count"] = len(mirrors)
        canonical.append(row)
    # MI-001 refuses to count unknown results/awards; observed people may be
    # inferred from secondary cards but labels retain their secondary nature.
    market = analyze_market(_as_mi001(seed, canonical, ontology))
    by_year = Counter(str(r["publication_date"])[:4] for r in canonical)
    by_family = Counter(r["family"] for r in canonical)
    by_scope = Counter(r["scope"] for r in canonical)
    by_tier = Counter(
        "primary_platform" if any(x["source_tier"] == "primary_platform"
                                  for x in r["evidence"]) else "third_party_only"
        for r in canonical
    )
    year_basis = Counter(r["date_basis"] for r in canonical)
    no_winner = sum(r.get("winner") is None for r in canonical)
    notices = sorted(canonical, key=lambda r: (r["publication_date"], r["id"]))
    direct_buyers = Counter(
        (r.get("customer") or {}).get("name")
        for r in canonical if (r.get("customer") or {}).get("name")
        and "Не раскрыт" not in r["customer"]["name"]
    )
    probe_summary = {
        "attempts": len((access_probe or {}).get("results", [])),
        "statuses": Counter(
            row.get("status", "unknown")
            for row in (access_probe or {}).get("results", [])
        ),
    }
    return {
        "schema_version": "power-quality-pilot-report/0.1",
        "window_from": seed["window_from"], "window_to": seed["window_to"],
        "as_of": seed["as_of"], "population_completeness": "UNKNOWN",
        "market_size_rub": None, "verified_award_equipment_spend_rub": None,
        "verified_award_count": 0, "verified_winner_count": 0,
        "seed_records": len(records), "distinct_procedure_lots": len(canonical),
        "mirror_duplicates_removed": len(records) - len(canonical),
        "period_sample_counts": dict(sorted(by_year.items())),
        "category_counts": dict(sorted(by_family.items())),
        "work_package_counts": dict(sorted(by_scope.items())),
        "source_evidence_tiers": dict(sorted(by_tier.items())),
        "date_basis_counts": dict(sorted(year_basis.items())),
        "records_without_verified_winner": no_winner,
        "buyers_in_seed": [
            {"name": name, "procedure_count": count}
            for name, count in sorted(
                direct_buyers.items(), key=lambda row: (-row[1], row[0])
            )
        ],
        "eis_access_probe": {
            "attempts": probe_summary["attempts"],
            "statuses": dict(probe_summary["statuses"]),
        },
        "market_model": market,
        "leads": notices,
        "limitations": [
            "Curated examples are not a population sample and cannot measure Russian TAM or growth.",
            "No verified winning bidder, EPC prime or named designer was established from a primary award protocol.",
            "Secondary platform statements of a closed procurement or contract are not registry-verified awards.",
            "An absent price or 0-ruble placeholder is unknown, not a 0-ruble contract.",
            "The 2026 dates include one deadline substituted for missing publication date and a secondary publication date; exclude those from pure publication-year trends.",
            "An EPC procurement envelope must not be counted as Power Quality hardware turnover.",
        ],
    }


def render_pilot_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Power Quality — пилот исследования закупок",
        f"Период {result['window_from']} — {result['window_to']}, срез {result['as_of']}.",
        "**Это доказательная пилотная выборка, НЕ полный российский рынок.**",
        f"Уникальных релевантных процедур/лотов: **{result['distinct_procedure_lots']}**.",
        f"Проверенных договоров с подтверждёнными победителями: **{result['verified_award_count']}**.",
        "Суммарный размер рынка: **не определён**. Сумма неизвестных контрактов НЕ равна нулю.",
        "",
        "## Найденные процедуры (цена договора и победитель НЕ подтверждены)",
        "| Год* | Закупка/ЭТП | Заказчик | Содержание | Тип | Источник |",
        "|---|---|---|---|---|---|",
    ]
    for item in result["leads"]:
        first = item["evidence"][0]
        customer = (item.get("customer") or {}).get("name") or "Не установлен"
        desc = item["description"].replace("|", "/")
        lines.append(
            f"| {item['publication_date'][:4]} | {item['procedure_id'] or 'ID не раскрыт'} "
            f"({item['platform']}) | {customer} | {desc} | {item['scope']} | "
            f"[карточка]({first['url']}) |"
        )
    lines.extend([
        "",
        "*Год — год указанной в карточке даты; если дата не является датой публикации, это отдельно зафиксировано в JSON.",
        "",
        "## Сводка наблюдаемой выборки",
        f"Категории: {result['category_counts']}.",
        f"Пакеты: {result['work_package_counts']}.",
        f"Уровень источника: {result['source_evidence_tiers']}.",
        f"Проверка прямого поиска ЕИС: {result['eis_access_probe']}.",
        "",
        "## Приоритет первичной технической квалификации",
    ])
    for row in result["buyers_in_seed"][:12]:
        lines.append(
            f"- **{row['name']}** — найдено процедур: {row['procedure_count']}; "
            "уточнить актуальный проект, ТЗ, проектировщика/EPC и допустимые аналоги."
        )
    lines += [
        "", "## Ограничения",
        *[f"- {v}" for v in result["limitations"]],
        "",
        "## Практические гипотезы выхода",
        "- **ЛУКОЙЛ-Западная Сибирь**: два самостоятельных поиска УКРМ — выяснить результаты обоих договоров и будущую спецификацию, не считать их уже заключёнными.",
        "- **Кузбассразрезуголь**: 3 СТАТКОМ для двух разрезов — предложить техническую квалификацию и сервис; победитель не установлен.",
        "- **Морской порт Суходол**: динамическая компенсация с фильтрацией в составе работ под ключ — выяснить проектную команду и EPC, не заявлять неизвестного победителя.",
        "- **Инженерно-Строительная Компания / ЦОД РУСАЛ**: вход через проектную цепочку комплектации; юридический EPC-подрядчик по протоколу пока не подтверждён.",
        "- **Башкирские распределительные электрические сети**: несостоявшееся проектирование УКРМ на ПС Пионерская — выяснить, будет ли повторный конкурс.",
        "- **Лебединский ГОК и ПС Могоча**: сервис существующих СТАТКОМ; не приравнивать ТО к закупке нового оборудования.",
        "",
        "## Действия для полноценного анализа",
        "1. Выполнить независимое первичное подтверждение номера, версии, протокола, договора и победителя каждой записи.",
        "2. Подключить полные исторические источники ЕИС и коммерческих ЭТП с проверкой полномочий и охвата по месяцам.",
        "3. Проиндексировать технические приложения EPC и ведомости объемов работ, подтвердить смысловое совпадение и долю оборудования.",
        "4. Только после сверки всего доступного реестра считать стоимость оборудования и доли EPC/поставщиков.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audited public Power Quality procurement sample")
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--access-probe", type=Path)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.seed, args.ontology, args.json_out, args.md_out]
    if args.access_probe:
        paths.append(args.access_probe)
    if len({p.resolve() for p in paths}) != len(paths):
        parser.error("inputs and outputs must be different paths")
    seed = json.loads(args.seed.read_text(encoding="utf-8"))
    ontology = yaml.safe_load(args.ontology.read_text(encoding="utf-8"))
    probe = (json.loads(args.access_probe.read_text(encoding="utf-8"))
             if args.access_probe else None)
    report = analyze_pilot(seed, ontology, probe)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    args.md_out.write_text(render_pilot_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
