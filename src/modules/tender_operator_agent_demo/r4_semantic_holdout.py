"""Pre-registered, source-only holdout guard; never generates or signs legal gold.

The selected 20 competitive cases are evaluation-contaminated and cannot be
relabelled as unseen. This component freezes *only* real, independently
first-party-attested new notice IDs and evidence hashes before seeing labels
or SUT predictions. Existing benchmark_pipeline owns the label-freeze phase.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from src.modules.benchmark_pipeline.contract import canonical_sha256

SHA = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"\d{19}\Z")


class HoldoutLeakageError(ValueError):
    """Holdout is not independent from prior development evidence."""


def forbidden_development_sources(original_audit: Mapping[str, Any]) -> dict[str, set[str]]:
    """Immutable disjointness baseline built from formerly inspected originals."""
    coverage = original_audit["selected_original_notice_attachment_coverage"]["cases"]
    notices = original_audit["competitive_notices"]
    numbers = {c["registry_number"] for c in coverage}
    numbers.update(c["registry_number"] for c in notices)
    docs = {d["original_document_sha256"] for c in coverage for d in c["documents"]}
    zips = {c["original_zip_sha256"] for c in notices}
    xmls = {c["original_xml_sha256"] for c in notices}
    if len(numbers) < 20 or len(docs) < 43:
        raise ValueError("Historical development dataset is not fully supplied")
    if not all(SHA.fullmatch(value) for value in docs | zips | xmls):
        raise ValueError("Broken development evidence digest")
    return {
        "notice_numbers": numbers,
        "binary_sha256": docs,
        "zip_sha256": zips,
        "xml_sha256": xmls,
    }


def lock_unseen_real_cohort(
    candidates: list[dict[str, Any]],
    *,
    forbidden: Mapping[str, set[str]],
    source_set_id: str,
    locked_at_utc: str,
) -> dict[str, Any]:
    """Lock chosen source identities, not SUT outputs or expert answers.

    Inputs must come from a separately validated official-source receipt.
    Never trust unsupported HTML search, user-entered notice IDs, or an
    unverified archive claim as sufficient for a *real official* holdout.
    """
    from datetime import datetime

    if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", source_set_id):
        raise ValueError("Invalid source set ID")
    locked = datetime.fromisoformat(locked_at_utc)
    if locked.tzinfo is None:
        raise ValueError("Holdout lock timestamp must be timezone-aware")
    if not candidates:
        raise ValueError("No new original official procurements supplied")
    if len(candidates) != len({c["registry_number"] for c in candidates}):
        raise HoldoutLeakageError("Duplicate notice number in prospective holdout")
    rows = []
    cross_doc_sha: set[str] = set()
    for c in candidates:
        no = c["registry_number"]
        if NUMBER.fullmatch(no) is None:
            raise ValueError("Invalid official registry number in candidate")
        if c.get("attestation") != "VERIFIED_OFFICIAL_GETDOCSIP_XML_AND_BINARY":
            raise ValueError("Unverified candidate is not a blind real-EIS holdout")
        if c.get("source_document_stage") != "PRE_LABEL_PRE_SUT":
            raise HoldoutLeakageError("Holdout candidate was observed after labels or model output")
        zip_sha, xml_sha = c["official_zip_sha256"], c["official_xml_sha256"]
        doc_shas = c["binary_original_sha256"]
        if not isinstance(doc_shas, list) or not doc_shas:
            raise ValueError("No official original document digests in candidate")
        if not all(isinstance(v, str) and SHA.fullmatch(v) for v in [zip_sha, xml_sha, *doc_shas]):
            raise ValueError("Invalid source digest; cannot attest independence")
        if len(set(doc_shas)) != len(doc_shas):
            raise HoldoutLeakageError("Repeated source binary in one case")
        if no in forbidden["notice_numbers"]:
            raise HoldoutLeakageError("Previously inspected procurement in held-out cohort")
        if zip_sha in forbidden["zip_sha256"] or xml_sha in forbidden["xml_sha256"]:
            raise HoldoutLeakageError("Identical previous official notice source archive")
        if set(doc_shas) & forbidden["binary_sha256"]:
            raise HoldoutLeakageError("Previously inspected original attachment copied into holdout")
        if set(doc_shas) & cross_doc_sha:
            raise HoldoutLeakageError("Attachment reused across holdout cases")
        cross_doc_sha.update(doc_shas)
        rows.append({
            "registry_number": no,
            "official_zip_sha256": zip_sha,
            "official_xml_sha256": xml_sha,
            "original_attachment_sha256": sorted(doc_shas),
            "source_attestation": "OFFICIAL_EIS_FIRST_PARTY_SHA_VERIFIED",
            "blind_legal_gold": "NOT_PREPARED",
            "sut_exposure": "FORBIDDEN_UNTIL_GOLD_FREEZE",
        })
    # Ordering is source-identity based; no tender title or perceived difficulty.
    ordered = sorted(rows, key=lambda x: x["registry_number"])
    evidence_sha = canonical_sha256(ordered)
    result = {
        "source_set_id": source_set_id,
        "locked_at_utc": locked_at_utc,
        "selection": "PRE_REGISTERED_SOURCE_IDS_NO_SEMANTIC_INSPECTION",
        "case_count": len(ordered),
        "cases": ordered,
        "case_evidence_sha256": evidence_sha,
        "gold_freeze_status": "PENDING_INDEPENDENT_EXPERT",
        "sut_run_authorized": False,
        "semantic_precision": None,
        "semantic_recall": None,
        "bid_ready": False,
    }
    result["immutable_lock_sha256"] = canonical_sha256({
        k: v for k, v in result.items() if k != "immutable_lock_sha256"
    })
    return result


def verify_cohort_lock(lock: Mapping[str, Any]) -> None:
    """Prevents quietly changing the sample after errors are seen."""
    expected = canonical_sha256({k: v for k, v in lock.items() if k != "immutable_lock_sha256"})
    if lock.get("immutable_lock_sha256") != expected:
        raise HoldoutLeakageError("Holdout was edited after pre-registration")
    if lock["case_evidence_sha256"] != canonical_sha256(lock["cases"]):
        raise HoldoutLeakageError("Source identities changed after holdout lock")
    if lock.get("gold_freeze_status") != "PENDING_INDEPENDENT_EXPERT":
        raise HoldoutLeakageError("This cohort is not in the source-only blind phase")
    if lock.get("sut_run_authorized") is not False:
        raise HoldoutLeakageError("SUT may not inspect pre-gold source lock")


def semantic_metrics_or_not_measured(
    *, holdout_lock: Mapping[str, Any], human_gold_freeze_receipt: Mapping[str, Any] | None,
    sut_run_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Never manufacture semantic accuracy before independently frozen gold.

    The existing benchmark_pipeline separately enforces label evidence
    references and the order evaluator_bundle → label freeze → SUT output.
    """
    verify_cohort_lock(holdout_lock)
    if human_gold_freeze_receipt is None or sut_run_receipt is None:
        return {
            "status": "NOT_MEASURED",
            "precision": None,
            "recall": None,
            "reason": "Independent legal labels and/or later SUT output are absent",
            "n_gold_cases": 0,
            "bid_ready": False,
        }
    raise ValueError(
        "Route actual frozen gold and later SUT artifacts through benchmark_pipeline "
        "comparison; generic holdout intake never certifies a legal accuracy metric"
    )
