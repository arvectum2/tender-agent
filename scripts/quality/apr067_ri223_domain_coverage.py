"""Development-only coverage of fixed probes on receipt-bound archived cases."""
from __future__ import annotations

import json
import time

from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    build_archived_review,
)

COMPLETE = ("32616444788","32616445632","32616445795","32616445866","32616447910")
INCOMPLETE = "32616376947"
DOMAINS = ("technical_scope","qualification","application","evaluation","contract",
           "participation","schedule","payment","security")


def case_measure(number, packet, elapsed_seconds):
    assert number in COMPLETE
    assert packet["status"] == "RI223_ARCHIVED_REVIEW_ONLY", (number,packet.get("reason"))
    inv = packet["inventory"]
    assert inv["archived_bytes_complete"] and inv["projection_complete"]
    assert not packet["go_eligible"] and not packet["requirements_verified"]
    assert not packet["current_revision_attested"] and not packet["external_action_allowed"]
    assert packet["decision"] == "NOT_DECIDED"
    domains = packet["domains"]
    assert tuple(d["domain"] for d in domains) == DOMAINS
    result = {}
    for domain in domains:
        citations = domain["citations"]
        assert domain["status"] == ("NEEDS_HUMAN_DOCUMENT_REVIEW" if citations else "NO_CITED_DOCUMENT_EXCERPT")
        assert not domain["requirements_verified"]
        assert len(citations) <= 2
        assert all(len(c["original_sha256"]) == 64 for c in citations)
        result[domain["domain"]] = len(citations)
    assert packet["source_backed_domains"] == sum(n > 0 for n in result.values())
    return {"case":number,"counts":result,"elapsed_seconds":round(elapsed_seconds,3),
            "originals":inv["originals_verified"],"members":inv["members_verified"],
            "searchable_candidates":inv["saved_searchable_candidates"]}


def summarize(rows, incomplete_refused):
    assert incomplete_refused is True
    assert tuple(sorted(r["case"] for r in rows)) == COMPLETE
    assert all(tuple(r["counts"]) == DOMAINS for r in rows)
    covered = {d:sum(r["counts"][d]>0 for r in rows) for d in DOMAINS}
    return {"scope":"ARCHIVED_LEXICAL_ORIGINAL_QUOTE_COVERAGE_ONLY",
            "complete_cases":len(rows),"incomplete_cases_refused":1,
            "probe_count":len(rows)*len(DOMAINS),"probes_with_citations":sum(covered.values()),
            "domain_cases_with_citations":covered,
            "citation_occurrences":sum(sum(r["counts"].values()) for r in rows),
            "cases":sorted(rows,key=lambda r:r["case"]),
            "semantic_precision":None,"semantic_recall":None,"current_source_accuracy":None,
            "human_gold":None,"commercial_acceptance":False,"rolling_slo":False}


def measure_runs(runs, all_runs, root, incomplete_refused):
    # RAR is opaque in default intake; use exact receipt-bound expansion for this measurement.
    from src.modules.tender_operator_agent_demo.ri223_offline_intake import (
        import_archive,
    )

    number="32616445795"
    case_root=root/number
    complete_runs={**all_runs,number:import_archive(runs,case_root/"ri223-soap.zip",number,
                                attachments=[case_root/"attachments/01-3727.rar"],expand_rar=True)}
    rows=[]
    for number,run_id in sorted(complete_runs.items()):
        run,meta=checked_search_run(run_id)
        start=time.monotonic()
        packet=build_archived_review(run_id,run,meta)
        row=case_measure(number,packet,time.monotonic()-start)
        rows.append(row)
        print("APR067_RI223_DOMAIN_CASE",json.dumps(row,ensure_ascii=False),flush=True)
    print("APR067_RI223_DOMAIN_COVERAGE_PASS",json.dumps(summarize(rows,incomplete_refused),ensure_ascii=False),flush=True)
