"""Post-acceptance independent ChatGPT / Tender Agent comparison intake.

No model is called here. This OFFLINE gate accepts source-bounded structured
metadata from two genuine independent reviews, records disagreement status,
and emits three unreviewed manual candidates for the EXISTING owner-internal
Procurement LLM corpus. Agreement is NEVER human/legal gold.

Requires an existing formally accepted Tender Agent technical gate, matching
document SHA on both reviews, and an independent run artifact per evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from scripts.procurement_llm.import_candidates import _manual_payload_items
from src.modules.procurement_learning_corpus.service import validate_candidate

HEX = re.compile(r"[a-f0-9]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9._:-]{4,120}\Z")
FIELDS = {
    "procedure_status",
    "application_deadline",
    "subject_and_scope",
    "qualification_requirements",
    "technical_requirements",
    "financial_requirements",
    "supplier_eligibility",
    "risks",
    "recommended_next_action",
}
EVALUATORS = ("chatgpt", "tender_agent")
MAX_CLAIMS = 60
SCHEMA = "procurement_dual_review_post_acceptance_v1"
MAX_INPUT_BYTES = 160_000


class DualReviewError(ValueError):
    """Unconfirmed post-acceptance source or unsafe review assertion."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_hash(v: object, field: str) -> str:
    if not isinstance(v, str) or not HEX.fullmatch(v):
        raise DualReviewError(f"invalid original SHA for {field}")
    return v


def _iso(v: object) -> str:
    if not isinstance(v, str):
        raise DualReviewError("missing timestamp")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as exc:
        raise DualReviewError("invalid observation timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise DualReviewError("naive observation timestamp")
    return dt.isoformat()


def _identifier(v: object, name: str) -> str:
    if not isinstance(v, str) or not IDENT.fullmatch(v):
        raise DualReviewError("invalid identifier " + name)
    return v


def _event_id(source_ref: str, source_sha: str, label: str, value_sha: str) -> str:
    digest = sha(f"{source_ref}:{source_sha}:{label}:{value_sha}".encode())[:32]
    return f"ta-dual:{label}:{digest}"


def _event(case: dict, *, label: str, artifact_sha: str, data: dict) -> dict:
    event = {
        "event_id": _event_id(
            case["procurement_ref"], case["source_manifest_sha256"], label, artifact_sha
        ),
        "procurement_ref": case["procurement_ref"],
        "participation": "reviewed_only",
        "review_state": "source_documented",
        "source_role": "development_exposed",
        "event_type": "post_acceptance_dual_" + label,
        "source_manifest_sha256": case["source_manifest_sha256"],
        "technical_acceptance_evidence_sha256": case["acceptance_evidence_sha256"],
        "technical_acceptance_status": "accepted",
        "evaluation_independent": True,
        "owner_internal_only": True,
        "human_adjudication_completed": False,
        "legal_gold": False,
        "model_gold": False,
        "training_labels": "NOT_REVIEWED",
        "training_promotion": False,
        "automatic_label_generation": False,
        "source_payload_is_only_metadata": True,
        "raw_model_output_copied": False,
        "owner_bid_go": False,
        "artifacts": data,
    }
    candidate = _manual_payload_items({
        "schema": "manual-candidate-import-v1", "items": [event]
    })[0]
    validate_candidate(candidate)
    return event


def compile_case(case: dict) -> dict:
    if not isinstance(case, dict) or case.get("schema") != SCHEMA:
        raise DualReviewError("unknown source comparison schema")
    ref = _identifier(case.get("procurement_ref"), "procurement_ref")
    source = _require_hash(case.get("source_manifest_sha256"), "source manifest")
    acceptance = case.get("technical_acceptance")
    if not isinstance(acceptance, dict) or set(acceptance) != {
        "status", "evidence_sha256", "accepted_at", "record_ref"
    }:
        raise DualReviewError("missing explicit technical acceptance evidence")
    if acceptance["status"] != "accepted":
        raise DualReviewError("dual comparison premature before actual acceptance")
    _identifier(acceptance["record_ref"], "acceptance record ref")
    _require_hash(acceptance["evidence_sha256"], "acceptance evidence")
    accepted_at = datetime.fromisoformat(_iso(acceptance["accepted_at"]))
    raw_docs = case.get("source_document_sha256")
    if (not isinstance(raw_docs, list) or not 1 <= len(raw_docs) <= 200
            or len(raw_docs) != len(set(raw_docs))):
        raise DualReviewError("missing/duplicate source document hashes")
    documents = {_require_hash(d, "original doc") for d in raw_docs}
    reviews = case.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise DualReviewError("two independent reviews required")
    by = {}
    for review in reviews:
        if not isinstance(review, dict) or review.get("evaluator") not in EVALUATORS:
            raise DualReviewError("wrong evaluator")
        evaluator = review["evaluator"]
        if evaluator in by:
            raise DualReviewError("same reviewer cannot double count")
        if review.get("source_manifest_sha256") != source:
            raise DualReviewError("not exactly same source pack/version")
        _identifier(review.get("run_ref"), "original independent run")
        if not isinstance(review.get("model_label"), str) or not 2 <= len(review["model_label"]) <= 120:
            raise DualReviewError("missing reviewer model provenance")
        _require_hash(review.get("prompt_sha256"), "independent prompt")
        artifact_sha = _require_hash(review.get("output_artifact_sha256"), "run artifact")
        at = datetime.fromisoformat(_iso(review.get("completed_at")))
        if at < accepted_at:
            raise DualReviewError("run predates technical acceptance")
        claims = review.get("claims")
        if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
            raise DualReviewError("no bounded evaluation claims")
        mapped = {}
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != {
                "field", "value_sha256", "source_document_sha256"
            }:
                raise DualReviewError("unexpected raw field/claim metadata")
            field = claim["field"]
            if field not in FIELDS or field in mapped:
                raise DualReviewError("unrecognized or repeated claim field")
            value = _require_hash(claim["value_sha256"], "normalized claim value")
            evidence = claim["source_document_sha256"]
            if not isinstance(evidence, list) or not evidence or len(evidence) > 15:
                raise DualReviewError("claim must cite at least one verified original document")
            if any(_require_hash(d, "cited source") not in documents for d in evidence):
                raise DualReviewError("claim cites document outside shared original pack")
            mapped[field] = {"value_sha256": value, "citations": sorted(set(evidence))}
        by[evaluator] = {"review": review, "claims": mapped, "artifact": artifact_sha}
    if (by["chatgpt"]["review"]["run_ref"] == by["tender_agent"]["review"]["run_ref"]
            or by["chatgpt"]["artifact"] == by["tender_agent"]["artifact"]):
        raise DualReviewError("not demonstrably independent outputs")
    case_ref = {
        "procurement_ref": ref,
        "source_manifest_sha256": source,
        "acceptance_evidence_sha256": acceptance["evidence_sha256"],
    }
    events = []
    for evaluator in EVALUATORS:
        r = by[evaluator]
        events.append(_event(case_ref, label=evaluator, artifact_sha=r["artifact"], data={
            "run_ref": r["review"]["run_ref"],
            "source_document_count": len(documents),
            "model_label": r["review"]["model_label"],
            "prompt_sha256": r["review"]["prompt_sha256"],
            "output_artifact_sha256": r["artifact"],
            "completed_at": r["review"]["completed_at"],
            "claim_count": len(r["claims"]),
            "claim_hashes": r["claims"],
        }))
    all_fields = sorted(set(by["chatgpt"]["claims"]) | set(by["tender_agent"]["claims"]))
    status = {}
    for field in all_fields:
        left = by["chatgpt"]["claims"].get(field)
        right = by["tender_agent"]["claims"].get(field)
        if left is None or right is None:
            status[field] = "MISSING_IN_ONE_REVIEW"
        elif left["value_sha256"] == right["value_sha256"]:
            status[field] = "AGREE_NOT_GOLD"
        else:
            status[field] = "DISAGREE_REQUIRES_HUMAN_REVIEW"
    comparison = {
        "evaluator_run_refs": {
            evaluator: by[evaluator]["review"]["run_ref"] for evaluator in EVALUATORS
        },
        "evaluator_original_artifact_sha256": {
            evaluator: by[evaluator]["artifact"] for evaluator in EVALUATORS
        },
        "source_document_count": len(documents),
        "claim_comparison": status,
        "disagreements_or_missing": sum(v != "AGREE_NOT_GOLD" for v in status.values()),
        "source_agreement_is_not_legal_or_human_gold": True,
        "human_adjudication_required": True,
        "bid_authorized": False,
    }
    events.append(_event(
        case_ref,
        label="comparison",
        artifact_sha=sha(json.dumps(comparison, sort_keys=True).encode()),
        data=comparison,
    ))
    batch = {"schema": "manual-candidate-import-v1", "items": events}
    candidates = _manual_payload_items(batch)
    if len({c["observation_id"] for c in candidates}) != 3:
        raise DualReviewError("collision in independent dual-review event IDs")
    return {
        "candidate_batch": batch,
        "field_comparison": status,
        "disagreements_or_missing": comparison["disagreements_or_missing"],
        "human_adjudication_required": True,
        "training_promotion": False,
        "bid_authorized": False,
    }


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < MAX_INPUT_BYTES:
        raise DualReviewError("private source manifest missing or oversized")
    def unique(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise DualReviewError("duplicate JSON key")
            value[k] = v
        return value
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def write_private_batch(destination: Path, batch: dict, private_root: Path) -> None:
    if (private_root.is_symlink() or not private_root.is_dir() or destination.is_symlink()
            or destination.resolve().parent != private_root.resolve()
            or destination.suffix != ".json"):
        raise DualReviewError("private destination required; never Git/raw source")
    body = json.dumps(batch, ensure_ascii=False, indent=2) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf8") != body or destination.stat().st_mode & 0o077:
            raise DualReviewError("cannot overwrite existing immutable private receipt")
        return
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    result = compile_case(_read(args.case))
    if args.private_output:
        private_root = Path(
            "/Volumes/ArvectumSSD/Arvectum/private/tender-agent/pending-manual-evidence"
        )
        write_private_batch(args.private_output, result["candidate_batch"], private_root)
    print(json.dumps({
        "mode": "owner_private_pending" if args.private_output else "offline_dry_run",
        "independent_reviews": 2,
        "comparison_events": 1,
        "unreviewed_existing_canonical_candidates": 3,
        "disagreement_fields": result["disagreements_or_missing"],
        "training_promotion": False,
        "automatic_human_gold": False,
        "database_mutations": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
