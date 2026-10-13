"""Offline CZN qualification replay against ORIGINAL private EIS archive + scoring DOCX.

No network, tenant DB writes, LLM, bids or live external actions. The only
profile information comes from an explicitly owner-provided immutable snapshot.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from src.modules.company_profile_store.qualification_original_source import (
    OriginalScoringEvidence,
    extract_official_qualification_criterion,
)
from src.modules.company_profile_store.qualification_references import (
    CompletedContractReferenceSnapshot,
    assess_references,
)


def replay(
    *,
    archive_path: Path,
    scoring_docx_path: Path,
    receipt_path: Path,
    owner_input_path: Path,
    as_of: date,
) -> dict:
    receipt = OriginalScoringEvidence.model_validate(
        json.loads(receipt_path.read_text(encoding="utf-8"))
    )
    owner_input = json.loads(owner_input_path.read_text(encoding="utf-8"))
    snapshot = CompletedContractReferenceSnapshot.model_validate(
        owner_input["reference_fact_value"]
    )
    criterion = extract_official_qualification_criterion(
        original_archive_bytes=archive_path.read_bytes(),
        original_scoring_docx_bytes=scoring_docx_path.read_bytes(),
        trusted_receipt=receipt,
        analysis_date=as_of,
    )
    if owner_input.get("czn_source_bound_criterion") is not None:
        # This reference is a historical public audit fixture. Compare source
        # characteristics only; do NOT read its hand-authored weights as facts.
        prior = owner_input["czn_source_bound_criterion"]
        for key in (
            "procurement_number", "procurement_notice_version", "source_document_uid",
            "source_document_sha256", "application_deadline_date",
        ):
            if prior.get(key) != getattr(criterion, key).isoformat() if key == "application_deadline_date" else prior.get(key) != getattr(criterion, key):
                raise ValueError("Original current EIS source differs from archived owner input")
    result = assess_references(
        customer_id="arvectum-research-only",
        criterion=criterion,
        snapshot=snapshot,
        fact_source_type=owner_input.get("reference_fact_source_type"),
        fact_source_ref=owner_input.get("reference_fact_source_ref"),
    )
    return {
        "status": "ORIGINAL_EIS_DOCX_SCORE_EXTRACTED_NO_SIGNATURE",
        "scoring": criterion.model_dump(mode="json"),
        "owner_snapshot_as_of": snapshot.as_of_date.isoformat(),
        "owner_reference_count": len(snapshot.contracts),
        "recommendation": result.recommendation,
        "qualifying_contracts": result.qualifying_contracts,
        "legal_eligibility_assessed": False,
        "digital_signature_validated": False,
        "human_gold": False,
        "external_action_allowed": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--scoring-docx", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--owner-input", type=Path, required=True)
    p.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = p.parse_args()
    print(json.dumps(replay(
        archive_path=args.archive,
        scoring_docx_path=args.scoring_docx,
        receipt_path=args.receipt,
        owner_input_path=args.owner_input,
        as_of=args.as_of,
    ), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
