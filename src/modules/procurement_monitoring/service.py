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


def snapshot_from_tender(tender: Any) -> SourceSnapshot:
    from .schemas import DocumentState

    docs = []
    active_revisions: set[str] = set()
    for doc in tender.documents:
        meta = doc.raw_meta or {}
        revision = meta.get("notice_revision") or meta.get("revision")
        active = meta.get("revision_active")
        if active is True and revision is not None:
            active_revisions.add(str(revision))
        docs.append(DocumentState(
            source_document_id=doc.source_document_id or doc.document_identity_hash or doc.id,
            sha256=doc.sha256,
            revision=str(revision) if revision is not None else None,
            source_url=doc.file_url,
        ))
    ambiguity_reason = "active_revision_ambiguous" if len(active_revisions) > 1 else None
    notice_revision = next(iter(active_revisions)) if len(active_revisions) == 1 else None
    raw = tender.raw_payload or {}
    if notice_revision is None:
        candidate = raw.get("notice_revision") or raw.get("revision")
        notice_revision = str(candidate) if candidate is not None else None
    status = tender.status
    normalized = (status or "").strip().lower()
    cancelled = True if normalized in {"cancelled", "canceled", "аннулирована", "отменена", "отменено"} else None
    return SourceSnapshot(
        source=tender.source,
        external_id=tender.external_id,
        source_url=tender.eis_url or tender.platform_url,
        application_deadline=tender.application_deadline,
        nmck_amount=tender.nmck_amount,
        status=status,
        notice_revision=notice_revision,
        cancelled=cancelled,
        documents=docs,
        ambiguity_reason=ambiguity_reason,
    )


def create_watch(session: Any, target: Any) -> Any:
    from sqlalchemy import select

    from .models import ProcurementWatch
    existing = session.scalar(select(ProcurementWatch).where(ProcurementWatch.source == target.source, ProcurementWatch.external_id == target.external_id))
    if existing:
        return existing
    watch = ProcurementWatch(source=target.source, external_id=target.external_id, source_url=target.source_url, saved_search=target.saved_search)
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


def check_watch(session: Any, watch_id: str) -> AlertEvent | None:
    from sqlalchemy import select

    from src.modules.event_log.service import append_event_record
    from src.shared.errors import NotFoundError
    from src.tender_research.models import ProcurementTender

    from .models import (
        ProcurementWatch,
        ProcurementWatchEvent,
        ProcurementWatchSnapshot,
    )

    watch = session.get(ProcurementWatch, watch_id)
    if watch is None:
        raise NotFoundError(f"Procurement watch '{watch_id}' was not found")
    tender = session.scalar(select(ProcurementTender).where(ProcurementTender.source == watch.source, ProcurementTender.external_id == watch.external_id))
    if tender is None:
        raise NotFoundError(f"Watched procurement '{watch.source}:{watch.external_id}' was not found")
    current = snapshot_from_tender(tender)
    current_fp = snapshot_fingerprint(current)
    previous_row = session.scalar(select(ProcurementWatchSnapshot).where(ProcurementWatchSnapshot.watch_id == watch.id).order_by(ProcurementWatchSnapshot.created_at.desc(), ProcurementWatchSnapshot.id.desc()).limit(1))
    if previous_row is None:
        session.add(ProcurementWatchSnapshot(watch_id=watch.id, fingerprint=current_fp, payload=current.model_dump(mode="json")))
        session.commit()
        return None
    previous = SourceSnapshot.model_validate(previous_row.payload)
    diff = diff_snapshots(previous, current)
    event = build_alert_event(current, diff)
    if diff.outcome == "UNCHANGED":
        return None
    existing_event = session.scalar(select(ProcurementWatchEvent).where(ProcurementWatchEvent.event_key == event.event_key))
    if existing_event is not None:
        return event
    if current_fp != previous_row.fingerprint:
        session.add(ProcurementWatchSnapshot(watch_id=watch.id, fingerprint=current_fp, payload=current.model_dump(mode="json")))
    session.add(ProcurementWatchEvent(watch_id=watch.id, event_key=event.event_key, outcome=event.outcome, source_url=event.source_url, payload=event.model_dump(mode="json")))
    append_event_record(session, deal_id=None, event_code="procurement_watch_changed", source_module_id="procurement_monitoring", severity="WARNING" if event.outcome == "NEEDS_REVIEW" else "INFO", payload_json=event.model_dump(mode="json"))
    from src.modules.integration_outbox.service import enqueue_event
    enqueue_event(session, event_type="monitoring_alert", aggregate_type="procurement_watch", aggregate_id=watch.id, source_key=event.event_key, data={"outcome": event.outcome, "source": watch.source, "external_id": watch.external_id, "source_url": event.source_url})
    session.commit()
    return event


def list_feed(session: Any, watch_id: str | None = None) -> list[Any]:
    from sqlalchemy import select

    from .models import ProcurementWatchEvent
    query = select(ProcurementWatchEvent).order_by(ProcurementWatchEvent.created_at.desc(), ProcurementWatchEvent.id.desc())
    if watch_id:
        query = query.where(ProcurementWatchEvent.watch_id == watch_id)
    return list(session.scalars(query))
