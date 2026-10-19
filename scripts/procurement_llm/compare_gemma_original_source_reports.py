"""Mechanical reproducible comparison of previous fast and new Gemma runs.

Exact fact/field presence checks only. NOT automatic proof of substantive
correctness, legal eligibility, full 20-block scope, or verified human gold.
Source citations and original SHA are required before reading the rerun.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.procurement_llm.gemma_originals_quality_benchmark import (
    ARCHIVE_SHA,
    SECTIONS,
)

FACT_CHECKS = [
    ("Реальный номер закупки", "notice_info", r"0163200000326005243"),
    ("Способ: открытый конкурс", "notice_info", r"открыт\w* конкурс"),
    ("НМЦК 497 178,33 ₽", "subject", r"497\s*178[.,]33|497178[.,]33"),
    ("Окончание подачи 30.10.2026", "deadlines",
     r"2026-10-30|30[.]10[.]2026|30\s+октября\s+2026"),
    ("Время окончания 11:00", "deadlines", r"11:00"),
    ("Исполнение до 08.12.2026", "contract_terms",
     r"08[.]12[.]2026|8\s+декабря\s+2026|2026-12-08"),
    ("Гарантия 12 месяцев", "contract_terms", r"12\s+месяц|12\s+мес"),
    ("Квалификация 70%", "evaluation_criteria",
     r"квалификац\w*[^\n]{0,130}70\s*%|70\s*%[^\n]{0,130}квалификац"),
    ("Цена 30% в оценке", "evaluation_criteria",
     r"цен\w*[^\n]{0,130}30\s*%|30\s*%[^\n]{0,130}цен"),
    ("Техстек 1С-Битрикс", "technical_scope", r"1с\s*[-–]?\s*битрикс"),
    ("Поиск депутата: четыре вкладки", "technical_scope",
     r"4\s+вклад|четыр[её]х?\s+вклад"),
    ("Доступность для слабовидящих", "technical_scope", r"слабовид"),
    ("Исключить зарубежные зависимости", "technical_scope",
     r"зарубежн|иностранн\w* ресурс"),
    ("URL редиректы index.php", "technical_scope", r"index[.]php"),
]


def _old_sections(markdown: str) -> dict[str,str]:
    positions = list(re.finditer(r"(?m)^##\s+(\w+)[.]\s+", markdown))
    result = {}
    for i, match in enumerate(positions):
        tail = positions[i+1].start() if i+1<len(positions) else len(markdown)
        result[match.group(1)]=markdown[match.end():tail]
    return result


def _known_registry_ids(answer: str) -> list[str]:
    return re.findall(r"registry_number\s*[:=]\s*([0-9]{19,25})", answer, re.IGNORECASE)


def _registry_citations_exact(answer: str) -> bool:
    found = _known_registry_ids(answer)
    return bool(found) and all(value == "0163200000326005243" for value in found)


def compare(old_markdown: str, new_report: dict) -> dict:
    if (
        new_report.get("schema")!="gemma_12b_reasoning_xml_full_source_benchmark_v1"
        or new_report.get("source",{}).get("original_archive_sha")!=ARCHIVE_SHA
        or new_report.get("source",{}).get("official_docx_count")!=5
    ):
        raise ValueError("cannot compare different tender version/source package")
    original=_old_sections(old_markdown)
    enhanced={r["id"]:r["answer"] for r in new_report["sections"]
              if r["status"]=="completed"}
    fully_cited = {
        sec:answer for sec,answer in enhanced.items()
        if _registry_citations_exact(answer)
    }
    invalid_registry_sections=[
        sec for sec,answer in enhanced.items()
        if not _registry_citations_exact(answer)
    ]
    checks=[]
    for label,scope,regex in FACT_CHECKS:
        checks.append({
            "fact":label,
            "section":scope,
            "prior_found":bool(re.search(regex,original.get(scope,""),re.IGNORECASE)),
            "new_found":bool(re.search(regex,enhanced.get(scope,""),re.IGNORECASE)),
            "new_strictly_cited":bool(re.search(regex,fully_cited.get(scope,""),re.IGNORECASE)),
            "available_in_new_report":scope in enhanced,
        })
    subject_old=original.get("subject","")
    subject_new=enhanced.get("subject","")
    return {
        "schema":"arvectum_gemma_same_model_comparison_v1",
        "archive_source_sha256":ARCHIVE_SHA,
        "baseline_run_seconds":249.97,
        "baseline_id":"ee8b1140-1cc6-46ef-b1db-661931fac69a",
        "baseline_model":"arvectum-gemma4-12b-it-qat-q4_0",
        "baseline_mode":"fast_3_chunks_4000_chars_reasoning_off",
        "enhanced_mode":"direct_originals_22000_chars_reasoning_on",
        "enhanced_elapsed_first_ten_seconds":round(sum(
            x["model_seconds"] + x.get("previous_failed_attempt_seconds", 0)
            for x in new_report["sections"] if
            x["id"] in {section["id"] for section in SECTIONS[:10]}
        ),2),
        "enhanced_elapsed_total_seconds":round(sum(
            x["model_seconds"] + x.get("previous_failed_attempt_seconds", 0)
            for x in new_report["sections"]
        ),2),
        "failed_attempts_repeated_and_counted":sum(
            max(0, x.get("attempt_count", 1)-1) for x in new_report["sections"]
        ),
        "enhanced_completed_sections":len(enhanced),
        "enhanced_strictly_validated_sections":len(fully_cited),
        "sections_rejected_by_extra_registry_number_audit":invalid_registry_sections,
        "previous_claimed_15m_nmc":bool(re.search(r"15\s*000\s*000",subject_old)),
        "enhanced_subject_mentions_15m_without_semantic_verdict":bool(
            re.search(r"15\s*000\s*000", subject_new)
        ),
        "mechanical_checks":checks,
        "prior_matched_checks":sum(c["prior_found"] for c in checks),
        "enhanced_matched_checks":sum(c["new_found"] for c in checks),
        "enhanced_strictly_cited_matched_checks":sum(c["new_strictly_cited"] for c in checks),
        "known_limitation":"String matching is not semantic accuracy or legal GO; manual compare necessary.",
        "not_independent_chatgpt_dual_eval":True,
        "not_production_pg_analysis_record":True,
        "human_training_gold":False,
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old",type=Path,required=True)
    p.add_argument("--new",type=Path,required=True)
    args=p.parse_args()
    result=compare(args.old.read_text(encoding="utf8"),
                   json.loads(args.new.read_text(encoding="utf8")))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
