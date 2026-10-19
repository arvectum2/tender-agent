"""Conservative same-tender fast-vs-detailed source-citation audit.

This is NOT a legal assessment, human adjudication, or official tender status.
A lexical signal is reported separately from evidence and reviewed accuracy.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NUMBER = "0163200000326005243"
MODEL = "arvectum-gemma4-12b-it-qat-q4_0"

# Each item is explicitly a textual coverage clue, not verified legal accuracy.
CLAIMS = {
    "real_nmck_497178_33": r"497\s*178[,.]33|497178[,.]33",
    "application_deadline_oct30": r"30[.]10[.]2026|2026-10-30|30\s+октября\s+2026",
    "bid_deadline_11_msk": r"11:00",
    "contract_due_dec08": r"08[.]12[.]2026|2026-12-08|8\s+декабря\s+2026",
    "warranty_12_months": r"12\s+(?:месяц|мес\b)",
    "price_weight_30": r"(?:цен[ауы]|стоимост)[^\n]{0,120}30\s*%|30\s*%[^\n]{0,120}цен",
    "qualification_weight_70": r"квалификац[^\n]{0,120}70\s*%|70\s*%[^\n]{0,120}квалификац",
    "experience_sum_weight_80": r"(?:общая цена|сумм[ауы]|договор)[^\n]{0,140}80\s*%",
    "experience_count_weight_20": r"(?:количеств|число)[^\n]{0,140}20\s*%",
    "bitrix_platform": r"1\s*[сc][\s-]*битрикс",
    "dev1_site_migration": r"dev1[.]smoloblduma[.]ru",
    "adaptive_design": r"адаптив",
    "accessibility": r"слабовид",
    "foreign_resource_independence": r"зарубежн|иностранн[^\n]{0,80}ресурс",
    "deputy_search_four_tabs": r"(?:4|четыре|четырёх)\s+вклад",
    "yandex_metrica": r"яндекс[.]?метрик",
    "redirect_preserve_urls": r"редирект|перенаправлен",
    "index_php_removal": r"index[.]php",
    "event_sections": r"мероприят",
    "visually_accessible_news": r"новост",
    "no_bid_decision": r"no\s*bid|не\s+участвовать",
    "effort_estimate": r"\b(?:252|592|1086|1\s*086)\s*(?:ч|час)",
}

CITED_REGISTRY = re.compile(r"registry_number\s*[:=]\s*([0-9]{18,25})", re.IGNORECASE)
HEADINGS = re.compile(r"(?m)^##\s+(\w+)[.]\s+", re.IGNORECASE)


def evaluate_report(markdown: str) -> dict:
    if not markdown.startswith(f"# Анализ закупки {NUMBER}\n"):
        raise ValueError("report is not the pinned archival tender")
    if f"({MODEL})" not in markdown:
        raise ValueError("model differs from the true Gemma comparison")
    sections = list(HEADINGS.finditer(markdown))
    if len(sections) != 10:
        raise ValueError("report must have the same ten section identities")
    section_ids = [match.group(1) for match in sections]
    if len(set(section_ids)) != 10:
        raise ValueError("duplicate section heading")
    fragments = {
        match.group(1): markdown[match.start():(
            sections[idx + 1].start() if idx + 1 < len(sections) else len(markdown)
        )]
        for idx, match in enumerate(sections)
    }
    # Claims are source-review hints only. Text may itself be negated or quoted.
    hints = {
        name: bool(re.search(pattern, markdown, re.IGNORECASE))
        for name, pattern in CLAIMS.items()
    }
    mentioned_registry = CITED_REGISTRY.findall(markdown)
    malformed = sorted({
        number for number in mentioned_registry if number != NUMBER
    })
    subject = fragments.get("subject", "")
    mistaken_nmck = bool(re.search(
        r"нмцк[^\n]{0,100}15\s*000\s*000",
        subject, re.IGNORECASE,
    ))
    return {
        "section_ids": section_ids,
        "section_count": len(sections),
        "lexical_hints": hints,
        "lexical_hints_count": sum(hints.values()),
        "cited_registry_numbers_count": len(mentioned_registry),
        "malformed_cited_registry_numbers_count": len(malformed),
        "malformed_cited_registry_numbers": malformed,
        "wrong_15m_as_nmck_text_flag": mistaken_nmck,
        "source_citations_need_manual_verification": True,
        "technical_completeness_not_verified": True,
        "contract_facts_not_human_verified": True,
        "economic_go_no_go_not_decided": True,
    }


def compare(old: str, new: str) -> dict:
    before = evaluate_report(old)
    after = evaluate_report(new)
    if before["section_ids"] != after["section_ids"]:
        raise ValueError("not the same ten analysis question sections")
    improvements = [
        label for label in CLAIMS
        if after["lexical_hints"][label] and not before["lexical_hints"][label]
    ]
    regressions = [
        label for label in CLAIMS
        if before["lexical_hints"][label] and not after["lexical_hints"][label]
    ]
    return {
        "schema": "smolensk_gemma_same_model_canonical_rag_textual_audit_v1",
        "procurement_ref": NUMBER,
        "model": MODEL,
        "source_version": "official_getDocsIP_archived_v2",
        "baseline": before,
        "enhanced": after,
        "newly_mentioned_clues": improvements,
        "no_longer_mentioned_clues": regressions,
        "strictly_not_gold": True,
        "not_an_official_legal_conclusion": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(
        compare(args.old.read_text(encoding="utf-8"),
                args.new.read_text(encoding="utf-8")),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
