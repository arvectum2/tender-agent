"""Power Quality MI-003 reproducible bounded evaluation and coverage snapshot.

Gold here is independently *curated existing source cards*, not a national
hold-out sample. A match on title/description is not proof of hidden-TZ recall.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .portfolio_pipeline import monthly_coverage, validated_role_graph
from .power_quality_pilot import _records
from .technical_matching import _matching_terms

NEGATIVE_CONTROLS = [
    "Разработка SVG vector graphics файлов для корпоративного сайта",
    "Поставка кондиционеров и средств защиты растений",
    "Услуги компенсации вреда и компенсационные выплаты",
    "Организация музыкального мероприятия, фильтр высоких частот звука",
    "Услуги проектирования презентации PowerPoint и брендинга",
    "Поставка кабельных наконечников и крепёжных изделий",
    "Установка светильников на подстанции без оборудования PQ",
    "Монтаж локальной сети и серверов, техника информационной безопасности",
]

SOURCE_INVENTORY = [
    "EIS-44FZ", "EIS-223FZ", "Roseltorg", "B2B-Center",
    "Metal-IT", "Bidzaar", "Other-commercial",
]

WORK_PACKAGE_ACTION = {
    "supply": "Запросить техническую спецификацию, напряжение, диапазон мощности, условия аналогов и план следующих закупок",
    "epc": "Выяснить действующего технического заказчика, проектировщика и EPC; предложить совместную комплектацию только после подтверждения ролей",
    "design": "Уточнить судьбу ПИР и график утверждения проектных решений; предложить проверку характеристик и допустимых аналогов",
    "maintenance": "Выяснить установленную базу, сервисные потребности и возможные планы модернизации, не считать обслуживание новой поставкой",
}


def evaluate(seed: dict[str, Any], ontology: dict[str, Any]) -> dict[str, Any]:
    """Measure lexical matching only against labelled existing sample."""
    records = _records(seed, ontology)
    per_lead = []
    true_positive = 0
    for lead in records:
        matches = _matching_terms(lead["description"], ontology)
        found = {item["family"] for item in matches}
        labelled = lead["family"]
        confirmed_in_description = labelled in found
        true_positive += int(confirmed_in_description)
        per_lead.append({
            "seed_id": lead["id"],
            "labelled_family": labelled,
            "matched_families": sorted(found),
            "expected_label_found_in_description": confirmed_in_description,
            "description_sha256": hashlib.sha256(
                lead["description"].encode()
            ).hexdigest(),
            "source_tier": (
                "primary_platform"
                if any(ev["source_tier"] == "primary_platform" for ev in lead["evidence"])
                else "third_party_only"
            ),
            "publication_date_basis": lead["date_basis"],
        })
    false_positive_controls = [
        {"control_index": index, "text": text, "matched_families": [
            x["family"] for x in _matching_terms(text, ontology)
        ]}
        for index, text in enumerate(NEGATIVE_CONTROLS)
    ]
    grid = monthly_coverage(
        start=seed["window_from"], end=seed["window_to"],
        sources=SOURCE_INVENTORY,
        receipts=[
            {"source": "EIS-44FZ", "month": "2026-10", "status": "failed"},
            {"source": "EIS-223FZ", "month": "2026-10", "status": "failed"},
        ],
    )
    graph = validated_role_graph([], permitted_project_ids={
        str(row["project"]) for row in records if row.get("project")
    })
    reported_buyers = {}
    for lead in records:
        org = lead.get("customer") or {}
        if org.get("name") and "Не раскрыт" not in org["name"]:
            buyer = reported_buyers.setdefault(org["name"], {
                "name": org["name"], "inn_reported": org.get("inn"),
                "procedure_ids": [], "provenance": "secondary_or_platform_card",
                "role_verified_from_official_protocol": False,
            })
            buyer["procedure_ids"].append(lead["procedure_id"] or lead["id"])
    account_playbook = []
    grouped_leads: dict[str, list[dict[str, Any]]] = {}
    for lead in records:
        customer = lead.get("customer") or {}
        name = customer.get("name") or ""
        if not name or "Не раскрыт" in name:
            continue
        identity = customer.get("inn") or name
        grouped_leads.setdefault(identity, []).append(lead)
    for group in grouped_leads.values():
        first = group[0]
        scopes = sorted({row["scope"] for row in group})
        source_links = sorted({
            ev["url"] for row in group for ev in row["evidence"]
        })
        account_playbook.append({
            "buyer_name_reported": first["customer"]["name"],
            "buyer_inn_reported": first["customer"].get("inn"),
            "observed_procedures": len(group),
            "product_families": sorted({row["family"] for row in group}),
            "work_packages": scopes,
            "period_observations_only": sorted(row["publication_date"] for row in group),
            "candidate_project_names": sorted({
                str(row.get("project") or "") for row in group
            }),
            "initial_priority_hypothesis": (
                "P1" if len(group) > 1 or "epc" in scopes else "P2"
            ),
            "proposed_actions": [WORK_PACKAGE_ACTION[scope] for scope in scopes],
            "source_urls": source_links,
            "verified_current_open_opportunity": False,
            "verified_winning_supplier": None,
            "legal_role_of_epc_verified": False,
            "recommended_state": "manual_qualification_not_automated_outreach",
        })
    account_playbook.sort(key=lambda row: (
        row["initial_priority_hypothesis"], -row["observed_procedures"],
        row["buyer_name_reported"],
    ))
    return {
        "schema_version": "mi003-power-quality-evaluation/0.1",
        "window": [seed["window_from"], seed["window_to"]],
        "source_seed_sha256": None,  # computed by CLI from actual bytes
        "sample_type": "purposefully_discovered_public_leads_not_population",
        "gold_label_method": "existing manually curated procurement card family",
        "labelled_lead_count": len(records),
        "expected_family_found_count": true_positive,
        "sample_description_label_recall": (
            round(true_positive / len(records), 4) if records else None
        ),
        "negative_controls_count": len(NEGATIVE_CONTROLS),
        "negative_control_false_positives": sum(
            bool(v["matched_families"]) for v in false_positive_controls
        ),
        "negative_controls_are_synthetic": True,
        "per_lead": per_lead,
        "negative_controls": false_positive_controls,
        "coverage": grid,
        "project_role_graph": graph,
        "reported_buyers_unverified": sorted(
            reported_buyers.values(), key=lambda row: row["name"]
        ),
        "account_playbook_unreviewed": account_playbook,
        "known_winning_epc": [],
        "known_verified_designers": [],
        "verified_hardware_market_size_rub": None,
        "unpriced_relevant_procedures": len(records),
        "critical_caveats": [
            "Description-level recall on purposefully discovered examples is not recall on hidden technical annexes or the Russian procurement population.",
            "Synthetic negative controls are smoke/regression examples, not independently sampled false-positive prevalence.",
            "Per-month official EIS/commercial coverage denominator is unknown, no national TAM or historical growth claims.",
            "Buyer and engineering role from third-party procurement cards is unverified; no signed contract or winner inferred.",
            "Two EIS October 2026 failures represent source access errors, not zero relevant tenders.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MI-003 Power Quality: portfolio matching / evidence readiness",
        f"Reporting window: {report['window'][0]}..{report['window'][1]}.",
        "**Status:** source-limited technical matching evaluation, not national market research.",
        (f"Curated positive procurement descriptions: {report['labelled_lead_count']}; "
        f"correctly recognized family labels: {report['expected_family_found_count']}."),
        (f"Description-level labelled recall: {report['sample_description_label_recall']}. "
        "**Does NOT measure embedded EPC technical-annex recall.**"),
        (f"Synthetic negatives: {report['negative_controls_count']}; "
        f"false-positive controls: {report['negative_control_false_positives']}."),
        (f"Known buyer organization names in existing seed: {len(report['reported_buyers_unverified'])}; "
        "verified EPC/winners/designers from original protocols: 0."),
        (f"Tracked source-month slots: {report['coverage']['source_month_slots']}; "
        f"complete: {report['coverage']['verified_complete_slots']}; "
        "unknown: remainder. Zero verified completeness does NOT mean zero market."),
        "",
        "## Lead-level technical label evaluation",
        "| Lead | Family label | Matched | Source tier |",
        "|---|---|---|---|",
    ]
    for row in report["per_lead"]:
        lines.append(
            f"| {row['seed_id']} | {row['labelled_family']} | "
            f"{'yes' if row['expected_label_found_in_description'] else 'NO'} | "
            f"{row['source_tier']} |"
        )
    lines += [
        "", "## Initial sales qualification (not proven open tenders or EPC roles)",
        "| Priority | Reported buyer | Observed procedures | Next actions |",
        "|---|---|---:|---|",
    ]
    for account in report["account_playbook_unreviewed"]:
        lines.append(
            f"| {account['initial_priority_hypothesis']} | "
            f"{account['buyer_name_reported']} | "
            f"{account['observed_procedures']} | "
            f"{'; '.join(account['proposed_actions'])} |"
        )
    lines += [
        "", "## Available independently of live SOAP",
        "- Supplier upload intake: bounded text / file / URL through Data Platform SDK; source collection isolated by tenant + run.",
        "- Portfolio family proposals: exact/expanded synonyms and context control; supplier claim not automatically verified.",
        "- Search: Data Platform hybrid ranking within separately **authorized** procurement collections; exact chunk/document references and optional SHA-256.",
        "- Role graph: only explicitly reviewed, original signed contract / official protocol / primary project documents support EPC, designer and supplier edges.",
        "- Annual finance, TAM, competitor shares and full-Russia procurement count: NOT AVAILABLE until historical source and award coverage established.",
        "- PPTX support implemented separately in Data Platform PR #126; requires review + service rollout before this upload type is live.",
        "",
        "## Limitations",
    ]
    lines.extend(f"- {limitation}" for limitation in report["critical_caveats"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="MI003 PQ bounded labelled source audit")
    parser.add_argument("--seed", type=Path, required=True)
    parser.add_argument("--ontology", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    args = parser.parse_args()
    paths = [args.seed, args.ontology, args.json_out, args.md_out]
    if len({p.resolve() for p in paths}) != len(paths):
        parser.error("input and output paths may not alias")
    data = args.seed.read_bytes()
    seed = json.loads(data)
    ontology = yaml.safe_load(args.ontology.read_text(encoding="utf-8"))
    result = evaluate(seed, ontology)
    result["source_seed_sha256"] = hashlib.sha256(data).hexdigest()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    args.md_out.write_text(render_markdown(result))


if __name__ == "__main__":
    main()
