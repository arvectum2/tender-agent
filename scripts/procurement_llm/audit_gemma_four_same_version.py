"""Mechanical, source-citation-aware audit of one coherent Gemma four-section probe.

Every pass here remains candidate_unreviewed, never human/legal gold. The
source review layer must independently verify factual entailment.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NUMBER = "0163200000326005243"
MODEL = "arvectum-gemma4-12b-it-qat-q4_0"
IDS = ("subject", "customer_requirements", "evaluation_criteria", "contract_terms")
UUID = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![0-9a-f])", re.IGNORECASE
)
NMC = re.compile(r"(?<!\d)497\s*178[,.]33\s*(?:руб|₽)", re.IGNORECASE)
WRONG_NMC = re.compile(r"(?:НМЦК|начальная\s+максимальная\s+цен[аы])[^.\n]{0,90}15\s*000\s*000", re.IGNORECASE)
PERCENT = lambda value: re.compile(r"(?<!\d)" + str(value) + r"\s*%", re.IGNORECASE)


def audit(frozen: dict) -> dict:
    if (
        frozen.get("schema") != "smolensk_original_eis_four_section_repair_v1"
        or frozen.get("mode") != "source_only_local_gemma"
        or frozen.get("procurement_ref") != NUMBER
        or frozen.get("model") != MODEL
        or tuple(frozen.get("selected_section_ids", [])) != IDS
        or frozen.get("canonical_database_modified") is not False
        or frozen.get("saved_run") is not False
        or frozen.get("gold_promoted") is not False
        or frozen.get("legal_bid_go") is not False
    ):
        raise ValueError("not a read-only same-model pinned four-section source probe")
    sections = frozen.get("sections") or []
    if len(sections) != 4 or tuple(x.get("id") for x in sections) != IDS:
        raise ValueError("not all four original analysis sections are present exactly once")
    data = []
    for s in sections:
        answer = s.get("answer") or ""
        evidence = s.get("source_evidence") or []
        available_ids = {x.get("chunk_id") for x in evidence if
                         x.get("registry_number") == NUMBER and
                         x.get("tender_id") and
                         re.fullmatch(r"[0-9a-f]{64}", x.get("sha256_text") or "")}
        identifiers = UUID.findall(answer)
        citations_valid = bool(identifiers) and all(i in available_ids for i in identifiers)
        accepted = s.get("accepted") is True and not s.get("error") and bool(answer) and citations_valid
        facts = {
            "original_correct_nmc_497178_33": bool(NMC.search(answer)) if s["id"] == "subject" else None,
            "old_wrong_15m_as_nmck": bool(WRONG_NMC.search(answer)) if s["id"] == "subject" else None,
            "criteria_30_70_80_20": (
                all(PERCENT(v).search(answer) for v in (30,70,80,20))
                if s["id"] == "evaluation_criteria" else None
            ),
            "execution_security_0_5_percent": (
                bool(re.search(r"(?<!\d)0[,.]5\s*%", answer))
                if s["id"] == "contract_terms" else None
            ),
        }
        required_facts = True
        if s["id"] == "subject":
            required_facts = facts["original_correct_nmc_497178_33"] and not facts["old_wrong_15m_as_nmck"]
        elif s["id"] == "evaluation_criteria":
            required_facts = facts["criteria_30_70_80_20"]
        elif s["id"] == "contract_terms":
            required_facts = facts["execution_security_0_5_percent"]
        data.append({
            "section_id": s["id"],
            "guard_accepted": s.get("accepted") is True,
            "guard_error": s.get("error"),
            "cited_identifiers": len(identifiers),
            "cited_all_existing_original_chunks": citations_valid,
            "actual_model_attempts": s.get("attempts"),
            "elapsed_seconds": s.get("duration_seconds"),
            "key_source_facts_mentioned": bool(required_facts),
            "key_fact_indicators": facts,
            "mechanically_passed": bool(accepted and required_facts),
        })
    return {
        "schema": "smolensk_llama_cpp_same_run_four_section_evidence_audit_v1",
        "procurement_ref": NUMBER,
        "model": MODEL,
        "all_four_guard_accepted": all(item["guard_accepted"] for item in data),
        "all_four_citations_checked": all(item["cited_all_existing_original_chunks"] for item in data),
        "all_four_key_fact_signals": all(item["key_source_facts_mentioned"] for item in data),
        "all_four_mechanical_acceptance": all(item["mechanically_passed"] for item in data),
        "sections": data,
        "independent_human_legal_fact_verification_done": False,
        "training_gold": False,
        "bid_go": False,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_path", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.report_path.read_text(encoding="utf-8"))),
                     ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
