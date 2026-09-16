from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import AlertEvent, ChangedField, SourceDiff, SourceSnapshot

_MONITORED_FIELDS = (
    "application_deadline",
    "nmck_amount",
    "status",
    "notice_revision",
    "cancelled",
)


def _canonical_snapshot(snapshot: SourceSnapshot) -> dict[str, Any]:
    payload = snapshot.model_dump(mode="json")
    payload["documents"] = sorted(
        payload["documents"],
        key=lambda item: (
            item.get("source_document_id") or "",
            item.get("revision") or "",
            item.get("sha256") or "",
            item.get("source_url") or "",
        ),
    )
    return payload


def snapshot_fingerprint(snapshot: SourceSnapshot) -> str:
    canonical = json.dumps(
        _canonical_snapshot(snapshot),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _document_identity(snapshot: SourceSnapshot) -> list[tuple[str, str | None, str | None]]:
    return sorted(
        (doc.source_document_id, doc.revision, doc.sha256)
        for doc in snapshot.documents
    )


def diff_snapshots(previous: SourceSnapshot, current: SourceSnapshot) -> SourceDiff:
    previous_fp = snapshot_fingerprint(previous)
    current_fp = snapshot_fingerprint(current)

    if previous.source != current.source or previous.external_id != current.external_id:
        return SourceDiff(
            outcome="NEEDS_REVIEW",
            reason="watch_target_identity_changed",
            previous_fingerprint=previous_fp,
            current_fingerprint=current_fp,
        )
    if current.ambiguity_reason:
        return SourceDiff(
            outcome="NEEDS_REVIEW",
            reason=current.ambiguity_reason,
            previous_fingerprint=previous_fp,
            current_fingerprint=current_fp,
        )
    if previous_fp == current_fp:
        return SourceDiff(
            outcome="UNCHANGED",
            previous_fingerprint=previous_fp,
            current_fingerprint=current_fp,
        )

    changes: list[ChangedField] = []
    for field in _MONITORED_FIELDS:
        before = getattr(previous, field)
        after = getattr(current, field)
        if before != after:
            changes.append(ChangedField(field=field, before=before, after=after))

    before_documents = _document_identity(previous)
    after_documents = _document_identity(current)
    if before_documents != after_documents:
        changes.append(
            ChangedField(
                field="document_set",
                before=before_documents,
                after=after_documents,
            )
        )

    if not changes:
        return SourceDiff(
            outcome="NEEDS_REVIEW",
            reason="unsupported_source_state_change",
            previous_fingerprint=previous_fp,
            current_fingerprint=current_fp,
        )

    return SourceDiff(
        outcome="CHANGED",
        changes=changes,
        previous_fingerprint=previous_fp,
        current_fingerprint=current_fp,
    )


def build_alert_event(snapshot: SourceSnapshot, diff: SourceDiff) -> AlertEvent | None:
    if diff.outcome == "UNCHANGED":
        return None
    event_material = f"{snapshot.source}:{snapshot.external_id}:{diff.previous_fingerprint}:{diff.current_fingerprint}:{diff.outcome}"
    event_key = hashlib.sha256(event_material.encode("utf-8")).hexdigest()
    return AlertEvent(
        source=snapshot.source,
        external_id=snapshot.external_id,
        source_url=snapshot.source_url,
        event_key=event_key,
        outcome=diff.outcome,
        changes=diff.changes,
        reason=diff.reason,
    )
