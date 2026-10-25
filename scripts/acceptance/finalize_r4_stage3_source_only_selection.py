"""Finalize SHA-disjoint sources in original fixed rank without replacing failures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_semantic_holdout import (
    forbid_reuse_of_prior_blind_cohorts,
    forbidden_development_sources,
)
from src.modules.tender_operator_agent_demo.r4_stage3_independence_filter import (
    filter_attested_candidates_by_independence,
)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--immutable-discovery-receipt",type=Path,required=True)
    ap.add_argument("--official-candidate-receipt",type=Path,required=True)
    ap.add_argument("--development-audit",type=Path,required=True)
    ap.add_argument("--previous-blind-lock",type=Path,action="append",required=True)
    ap.add_argument("--private-audit-output",type=Path,required=True)
    ap.add_argument("--private-frozen-candidate-receipt",type=Path,required=True)
    args=ap.parse_args()
    if args.private_audit_output.exists() or args.private_frozen_candidate_receipt.exists():
        raise ValueError("Source-only stage3 audit cannot overwrite prior candidate decisions")
    if len(args.previous_blind_lock)!=2:
        raise ValueError("Both historical immutable blind cohorts must be supplied")
    selected=json.loads(args.immutable_discovery_receipt.read_text())
    results=json.loads(args.official_candidate_receipt.read_text())["cases"]
    sources=forbid_reuse_of_prior_blind_cohorts(
        forbidden_development_sources(json.loads(args.development_audit.read_text())),
        [json.loads(x.read_text()) for x in args.previous_blind_lock],
    )
    report=filter_attested_candidates_by_independence(
        immutable_discovery=selected,
        official_cases=results,
        previously_protected_numbers=sources["notice_numbers"],
        previously_protected_original_sha256=sources["binary_sha256"],
        previously_protected_zip_sha256=sources["zip_sha256"],
        previously_protected_xml_sha256=sources["xml_sha256"],
    )
    args.private_audit_output.parent.mkdir(parents=True,exist_ok=True)
    args.private_audit_output.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    args.private_frozen_candidate_receipt.write_text(json.dumps(
        report["accepted_source_only_cases"],sort_keys=True,ensure_ascii=False,indent=2,
    )+"\n")
    print("STAGE3_INDEPENDENT_SOURCE_CASES",len(report["accepted_source_only_cases"]),
          "REJECTED",len(report["excluded_cases_in_source_order"]),"NO_REPLACEMENTS")


if __name__=="__main__":
    main()
