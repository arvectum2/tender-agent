"""Safe append-only candidate intake for procurement data; never a training/gold writer."""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_PARTICIPATION = {"unknown", "considered", "reviewed_only", "submitted"}
_REVIEWS = {"source_documented", "owner_reported", "unverified_chat_recall", "system_recorded"}
_KINDS = {"development_e2e", "manual_review", "analysis_run", "legacy_report_artifact"}
_PROTECTED_SOURCE_ROLES = {"blind", "blind_holdout", "independent_gold", "r4_blind_holdout"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_candidate(row: dict) -> None:
    if row["event_kind"] not in _KINDS:
        raise ValueError("Unrecognised observation kind")
    if row["participation"] not in _PARTICIPATION or row["review_state"] not in _REVIEWS:
        raise ValueError("Invalid participation or review state")
    if row["training_status"] != "candidate_unreviewed":
        raise ValueError("Training labels/gold cannot be written via candidate intake")
    if not isinstance(row["payload_json"], dict):
        raise TypeError("Candidate payload must be an object")
    payload = row["payload_json"]
    if len(canonical(payload)) > 65536:
        raise ValueError("Candidate metadata payload exceeds 64 KiB")
    if any(payload.get(key) for key in ("raw_chat", "full_chat_transcript", "private_attachments", "api_key", "access_token")):
        raise ValueError("Raw chat contents or secrets cannot enter the candidate registry")
    if payload.get("signed_human_gold") or payload.get("legal_gold") or payload.get("model_gold"):
        raise ValueError("Human/legal gold cannot be imported as training candidates")
    if payload.get("protected_blind") is True or "blind_holdout" in payload.get("tags", []):
        raise ValueError("Protected blind cases cannot enter a development corpus")
    if str(payload.get("source_role", "")).lower() in _PROTECTED_SOURCE_ROLES:
        raise ValueError("Protected blind source role cannot enter development")
    source = payload.get("source") or {}
    if isinstance(source, dict) and str(source.get("source_role", "")).lower() in _PROTECTED_SOURCE_ROLES:
        raise ValueError("Protected blind source must remain outside training")
    if row["candidate_split"].lower() in {"blind", "blind_holdout", "independent_gold", "test_holdout"}:
        raise ValueError("Protected holdout split cannot be imported")
    if not _HEX.fullmatch(row["observation_id"]) or not _HEX.fullmatch(row["provenance_sha256"]):
        raise ValueError("Invalid source hash or immutable observation ID")
    if not row["procurement_ref"] or len(row["procurement_ref"]) > 256:
        raise ValueError("Invalid procurement reference")
    if row["visibility_scope"] == "tenant":
        if not row.get("customer_id"):
            raise ValueError("Tenant observation requires customer ID")
    elif row["visibility_scope"] == "owner_internal":
        if row.get("customer_id") is not None:
            raise ValueError("Owner-only imports cannot impersonate a tenant")
    else:
        raise ValueError("Unknown visibility scope")
    if row["participation"] == "submitted" and not payload.get("participation_evidence"):
        raise ValueError("Submitted participation requires evidence status")
    if row["event_kind"] == "analysis_run" and not payload.get("run_id"):
        raise ValueError("Analysis run capture requires saved run ID")


def learning_capture_enabled() -> bool:
    """Owner-approved forward capture defaults ON for both saved-run workflows.

    An explicit 0 disables in isolated tests / dedicated maintenance only.
    Unexpected values fail closed so a typo cannot silently omit evidence.
    Requires canonical Alembic 107; missing table rolls the run back.
    """
    setting = os.environ.get("TENDER_LEARNING_CAPTURE_ENABLED", "1")
    if setting not in {"0", "1"}:
        raise ValueError("TENDER_LEARNING_CAPTURE_ENABLED must be 0 or 1")
    return setting == "1"


def append_candidate(session: Session, row: dict) -> bool:
    """Append one unreviewed candidate within caller-owned transaction.

    Returns True on insert; a replay is False. Same key with altered content
    raises, rather than rewriting provenance. No commit/DDL/side effects.
    """
    validate_candidate(row)
    columns = {
        k: row[k] for k in (
            "observation_id", "event_kind", "procurement_ref", "source_ref",
            "provenance_sha256", "participation", "review_state", "training_status",
            "candidate_split", "visibility_scope", "customer_id", "payload_json",
        )
    }
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        statement = pg_insert(ProcurementLearningObservation).values(**columns)
    elif bind.dialect.name == "sqlite":
        statement = sqlite_insert(ProcurementLearningObservation).values(**columns)
    else:
        raise RuntimeError("Only existing PostgreSQL or disposable SQLite test DB supported")
    result = session.execute(
        statement.on_conflict_do_nothing(index_elements=["observation_id"]).returning(
            ProcurementLearningObservation.observation_id
        )
    )
    inserted_id = result.scalar_one_or_none()
    existing = session.get(ProcurementLearningObservation, row["observation_id"])
    if existing is None:
        raise RuntimeError("No persisted candidate after insert")
    for key, expected in columns.items():
        if getattr(existing, key) != expected:
            raise ValueError("Immutable observation ID collides with different provenance/payload")
    return inserted_id is not None


def make_analysis_candidate(run: Any) -> dict:
    """Index an already persisted run, not report text or new model-generated truth."""
    if not run.id:
        raise ValueError("Saved run ID required")
    payload = {
        "run_id": run.id,
        "registry_number": run.registry_number,
        "model": run.llm_model,
        "used_llm": run.used_llm,
        "status": run.status,
        "report_path": run.report_path,
        "sources_count": run.sources_count,
        "source": run.source,
        "full_raw_documents_copied": False,
        "participation_evidence": None,
    }
    owner = not bool(run.customer_id)
    return {
        "observation_id": digest({"kind": "analysis_run", "run_id": run.id}),
        "event_kind": "analysis_run",
        "procurement_ref": str(run.registry_number),
        "source_ref": "tender_analysis_runs:" + run.id,
        "provenance_sha256": digest(payload),
        "participation": "unknown",
        "review_state": "system_recorded",
        "training_status": "candidate_unreviewed",
        "candidate_split": "development_exposed",
        "visibility_scope": "owner_internal" if owner else "tenant",
        "customer_id": None if owner else run.customer_id,
        "payload_json": payload,
    }


def make_legacy_candidate(row: dict) -> dict:
    """Lossless metadata transition: preserves original SQLite row and payload."""
    kind = row["kind"]
    payload = json.loads(row["payload"])
    if kind == "development_e2e":
        reg = payload["registry_number"]
        identity = {"kind": "development_e2e", "reg": reg, "source_sha": payload["source"]["archived_zip_sha256"]}
        source_ref = "original_dev_e2e:" + str(reg)
    elif kind == "manual_review":
        identity = {"kind": "manual_review", "event_id": payload["event_id"]}
        source_ref = "historical_manual:" + payload["event_id"]
    else:
        raise ValueError("Unexpected legacy kind")
    if digest(identity) != row["observation_id"]:
        raise ValueError("Legacy observation ID has invalid immutable identity")
    return {
        "observation_id": row["observation_id"],
        "event_kind": kind,
        "procurement_ref": row["procurement_ref"],
        "source_ref": source_ref,
        "provenance_sha256": row["provenance_sha256"],
        "participation": row["participation"],
        "review_state": row["review_state"],
        "training_status": row["training_status"],
        "candidate_split": row["candidate_split"],
        "visibility_scope": "owner_internal",
        "customer_id": None,
        "payload_json": payload,
    }


def make_manual_candidate(event: dict, *, customer_id: str | None = None) -> dict:
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", event_id):
        raise ValueError("Stable manual event_id required")
    ref = event.get("procurement_ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("Procurement reference required")
    return {
        "observation_id": digest({"kind": "manual_review", "event_id": event_id}),
        "event_kind": "manual_review",
        "procurement_ref": ref.strip(),
        "source_ref": "manual:" + event_id,
        "provenance_sha256": digest(event),
        "participation": event.get("participation", "unknown"),
        "review_state": event.get("review_state", "unverified_chat_recall"),
        "training_status": "candidate_unreviewed",
        "candidate_split": "manual_candidate_not_blind",
        "visibility_scope": "tenant" if customer_id else "owner_internal",
        "customer_id": customer_id,
        "payload_json": event,
    }
