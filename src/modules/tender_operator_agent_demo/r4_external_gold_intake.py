"""External human gold intake: source quotes + cryptographic reviewer provenance.

No evaluator prompts, model predictions, or labels are created here. A public
key must be independently enrolled by the owner; generating a signature
from our own key cannot establish independent expertise.
"""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.modules.benchmark_pipeline.contract import (
    BenchmarkContractError,
    canonical_json,
    canonical_sha256,
    verify_manifest_source_files,
)
from src.modules.benchmark_pipeline.workflow import (
    assert_blind_evaluator_bundle,
    freeze_blind_labels,
    validate_blind_label_consistency,
)
from src.modules.tender_operator_agent_demo.r4_original_text_extract import (
    verified_document_text,
    verified_pdf_citation_pages,
)

_WS = re.compile(r"\s+")


def attestation_payload(
    evaluator_bundle: dict[str, Any],
    discovery_label: dict[str, Any],
    document_truth: dict[str, Any],
    *,
    reviewer_id: str,
    attested_at: str,
) -> bytes:
    """Exact bytes to be signed by the independently enrolled human reviewer."""
    if not reviewer_id or not attested_at:
        raise ValueError("Signed external reviewer identity/time required")
    return canonical_json({
        "purpose": "ARVECTUM_R4_INDEPENDENT_HUMAN_BLIND_GOLD_V1",
        "reviewer_id": reviewer_id,
        "attested_at": attested_at,
        "case_id": evaluator_bundle["case_id"],
        "evaluator_bundle_sha256": canonical_sha256(evaluator_bundle),
        "discovery_label_sha256": canonical_sha256(discovery_label),
        "document_truth_sha256": canonical_sha256(document_truth),
        "declares_no_prior_access_to_sut_results": True,
    })


def _quotes_exactly_grounded(
    evaluator_bundle: dict[str, Any],
    discovery_label: dict[str, Any],
    document_truth: dict[str, Any],
    source_root: Path,
) -> None:
    """Material discovery and asserted fact quotes must match source bytes.

    Only whitespace is normalized. Unsupported/scanned originals require
    verified manual transcriptions and are not silently accepted by this gate.
    """
    docs = {doc["path"]: doc for doc in evaluator_bundle["documents"]}
    all_evidence = []
    if discovery_label["label"] != "UNCLEAR":
        if not discovery_label["evidence"]:
            raise BenchmarkContractError("Scored discovery requires source-grounded quote")
        all_evidence.extend(discovery_label["evidence"])
    for fact in document_truth["facts"]:
        if fact["abstention"] == "ASSERTED":
            if not fact["evidence"]:
                raise BenchmarkContractError("ASSERTED gold requires exact original source")
            all_evidence.extend(fact["evidence"])
    text_cache: dict[str, str] = {}
    pdf_pages_cache: dict[str, list[str] | None] = {}
    for ref in all_evidence:
        name = ref["source_ref"]
        if name not in docs:
            raise BenchmarkContractError("Reviewer assertion must quote original binary, not URL")
        quote, locator = ref.get("quote"), ref.get("locator")
        if not isinstance(quote, str) or len(quote.strip()) < 12 or not locator:
            raise BenchmarkContractError("Source evidence needs human quote and locator")
        if name not in text_cache:
            original = (source_root.resolve() / name).resolve()
            try:
                original.relative_to(source_root.resolve())
            except ValueError as exc:
                raise BenchmarkContractError("Original evidence escapes source root") from exc
            payload = original.read_bytes()
            if hashlib.sha256(payload).hexdigest() != docs[name]["sha256"]:
                raise BenchmarkContractError("Original source binary SHA changed")
            try:
                text_cache[name] = verified_document_text(payload, original.name)
                pdf_pages_cache[name] = verified_pdf_citation_pages(payload, original.name)
            except (ValueError, OSError) as exc:
                raise BenchmarkContractError(
                    "Original unsearchable by text extractor; human source "
                    "transcription verification needed before freeze"
                ) from exc
        normalized = _WS.sub(" ", text_cache[name]).strip()
        source_quote = _WS.sub(" ", quote).strip()
        if source_quote not in normalized:
            raise BenchmarkContractError("Reviewer quote not verbatim from source original")
        pages = pdf_pages_cache[name]
        if pages is not None:
            page_match = re.fullmatch(r"PAGE-([1-9][0-9]*)", str(locator))
            if page_match is None:
                raise BenchmarkContractError("PDF citation needs a PAGE-N locator")
            index = int(page_match.group(1)) - 1
            if index >= len(pages) or source_quote not in _WS.sub(" ", pages[index]).strip():
                raise BenchmarkContractError("PDF citation quote not found on claimed page")
            continue
        # DOCX paragraph/table and XLSX cells have structural locators.
        docx_locator = re.fullmatch(
            r"PARAGRAPH-\d+|TABLE-\d+ ROW-\d+ CELL-\d+", str(locator),
        )
        xlsx_locator = re.fullmatch(
            r"SHEET-.+ CELL-[A-Z]+[1-9][0-9]*", str(locator),
        )
        first_line = text_cache[name].splitlines()[0]
        if first_line.startswith("SHEET-") and not xlsx_locator:
            raise BenchmarkContractError("XLSX evidence must locate the exact sheet/cell")
        if first_line.startswith(("PARAGRAPH-", "TABLE-")) and not docx_locator:
            raise BenchmarkContractError("DOCX evidence must locate the exact paragraph/cell")
        if docx_locator or xlsx_locator:
            matching_lines = [
                line for line in text_cache[name].splitlines()
                if line.startswith(locator + ": ")
            ]
            if len(matching_lines) != 1:
                raise BenchmarkContractError("Claimed source locator does not exist")
            value = matching_lines[0].split(": ", 1)[1]
            if source_quote not in _WS.sub(" ", value):
                raise BenchmarkContractError(
                    "Reviewer quote is not in claimed source paragraph or table cell"
                )


def verify_independent_expert_submission(
    *, evaluator_bundle: dict[str, Any],
    discovery_label: dict[str, Any],
    document_truth: dict[str, Any],
    source_manifest: dict[str, Any],
    original_source_root: Path,
    signed_attestation: dict[str, Any],
    trusted_reviewer_keys: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Verify against owner-enrolled public key; still not a legal opinion.

    Human expertise and role MUST have been established separately by Owner;
    identity by email, JSON declaration or signature alone is insufficient.
    """
    assert_blind_evaluator_bundle(evaluator_bundle)
    validate_blind_label_consistency(evaluator_bundle, discovery_label, document_truth)
    if source_manifest["case_id"] != evaluator_bundle["case_id"] or (
        canonical_sha256(source_manifest) != evaluator_bundle["case_manifest_sha256"]
    ):
        raise BenchmarkContractError("Evaluator bundle manifest changed after source freeze")
    verify_manifest_source_files(source_manifest, original_source_root)
    _quotes_exactly_grounded(
        evaluator_bundle, discovery_label, document_truth, original_source_root
    )

    reviewer = signed_attestation.get("reviewer_id")
    if (
        not isinstance(reviewer, str)
        or reviewer != discovery_label["evaluator"]
        or reviewer != document_truth["evaluator"]
        or reviewer not in trusted_reviewer_keys
    ):
        raise BenchmarkContractError("Independent reviewer identity is not enrolled")
    record = trusted_reviewer_keys[reviewer]
    if record.get("role") != "QUALIFIED_INDEPENDENT_LEGAL_EXPERT" or (
        record.get("owner_identity_verified") is not True
    ):
        raise BenchmarkContractError("Qualified independent reviewer trust is not owner-verified")
    if signed_attestation.get("no_prior_sut_access") is not True:
        raise BenchmarkContractError("Human reviewer blind isolation not declared")
    signed_time = signed_attestation.get("attested_at")
    signed_b64 = signed_attestation.get("ed25519_signature_b64")
    pub_b64 = record.get("ed25519_public_key_b64")
    if not all(isinstance(value, str) and value for value in (signed_time, signed_b64, pub_b64)):
        raise BenchmarkContractError("Detached reviewer signature or time missing")
    try:
        signed_dt = datetime.fromisoformat(signed_time)
        timestamps = [
            datetime.fromisoformat(evaluator_bundle["prepared_at"]),
            datetime.fromisoformat(discovery_label["evaluated_at"]),
            datetime.fromisoformat(document_truth["evaluated_at"]),
        ]
        if signed_dt.tzinfo is None or any(t.tzinfo is None for t in timestamps):
            raise ValueError("External review timestamps must include timezone")
        if signed_dt < max(timestamps):
            raise ValueError("Reviewer cannot sign labels before they are written")
    except (ValueError, TypeError) as exc:
        raise BenchmarkContractError("Human reviewer attestation timestamp invalid") from exc
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_b64, validate=True))
        signature = base64.b64decode(signed_b64, validate=True)
        public.verify(signature, attestation_payload(
            evaluator_bundle, discovery_label, document_truth,
            reviewer_id=reviewer, attested_at=signed_time,
        ))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise BenchmarkContractError("Detached human reviewer signature invalid") from exc
    return {
        "case_id": evaluator_bundle["case_id"],
        "reviewer_id": reviewer,
        "verified_at": signed_time,
        "evaluator_bundle_sha256": canonical_sha256(evaluator_bundle),
        "discovery_label_sha256": canonical_sha256(discovery_label),
        "document_truth_sha256": canonical_sha256(document_truth),
        "status": "SIGNATURE_AND_SOURCE_QUOTE_PRECHECK_PASSED",
        "independent_legal_opinion_issued_by_this_tool": False,
    }


def freeze_verified_external_gold(
    *, evaluator_bundle: dict[str, Any],
    discovery_label: dict[str, Any],
    document_truth: dict[str, Any],
    source_manifest: dict[str, Any],
    original_source_root: Path,
    signed_attestation: dict[str, Any],
    trusted_reviewer_keys: dict[str, dict[str, Any]],
    frozen_at: str,
) -> dict[str, Any]:
    """Atomic signature/quote validation + canonical benchmark freeze.

    No caller-supplied "validated" status can grant permission to freeze.
    This only verifies the enrolled key, not the human's professional
    competence: Owner must independently vet the trust roster.
    """
    attested = verify_independent_expert_submission(
        evaluator_bundle=evaluator_bundle,
        discovery_label=discovery_label,
        document_truth=document_truth,
        source_manifest=source_manifest,
        original_source_root=original_source_root,
        signed_attestation=signed_attestation,
        trusted_reviewer_keys=trusted_reviewer_keys,
    )
    try:
        frozen = datetime.fromisoformat(frozen_at)
        signed = datetime.fromisoformat(attested["verified_at"])
    except (ValueError, TypeError) as exc:
        raise BenchmarkContractError("Invalid external-gold freeze timestamp") from exc
    if frozen.tzinfo is None or frozen <= signed:
        raise BenchmarkContractError("Gold must freeze strictly after human signature")
    return freeze_blind_labels(
        evaluator_bundle, discovery_label, document_truth, frozen_at=frozen_at,
    )
