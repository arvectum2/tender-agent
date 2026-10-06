from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.modules.daily_tender_run.manager_synthesis import synthesize_manager_brief
from src.modules.daily_tender_run.models import DailyTenderRun, DailyTenderRunItem
from src.modules.daily_tender_run.profiles import load_daily_tender_profile
from src.modules.daily_tender_run.schemas import (
    DailyTenderProfile,
    DailyTenderRunItemResponse,
    DailyTenderRunResponse,
    StartDailyTenderRunRequest,
)
from src.modules.tender_intake.schemas import CreateTenderIntakeRequest
from src.modules.tender_intake.service import create_tender_intake
from src.modules.tender_operator_agent_demo.procurement_discovery import (
    search_public_44fz,
)
from src.shared.db.base import utcnow
from src.shared.enums import DirectionType, InitialSourceType, TenderSourceType
from src.shared.errors import NotFoundError
from src.tender_research.pipeline import TenderResearchPipeline
from src.tender_research.rag.analysis_service import analyze_tender
from src.tender_research.rag.prepare_service import prepare_tender_for_analysis

_TERMINAL_REUSE_STATUSES = {"MANAGER_READY", "SCREENED_OUT", "DUPLICATE"}
_PROCESSABLE_STATUSES = {"SHORTLISTED", "PROCESSING"}
_MOSCOW = ZoneInfo("Europe/Moscow")


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"DTR-{stamp}-{uuid4().hex[:8]}"


def _registry_number(card: dict[str, Any]) -> str:
    for key in (
        "reestr_number",
        "registry_number",
        "notice_number",
        "procurement_number",
        "procurement_id",
    ):
        value = str(card.get(key) or "").strip()
        if value:
            return value
    return ""


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_deadline(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidates = (
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in candidates:
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=_MOSCOW)
        except ValueError:
            continue
        return parsed.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_MOSCOW)
    return parsed.astimezone(UTC)


def _fingerprint(card: dict[str, Any]) -> str:
    stable = {
        "registry_number": _registry_number(card),
        "title": card.get("title"),
        "customer_name": card.get("customer_name"),
        "initial_price": card.get("initial_price"),
        "deadline": card.get("deadline"),
        "status": card.get("status"),
        "source_url": card.get("source_url"),
        "publication_date": card.get("publication_date"),
    }
    return hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _screen_card(
    profile: DailyTenderProfile,
    card: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[str, float, list[str]]:
    now = now or datetime.now(UTC)
    title = str(card.get("title") or "").strip()
    customer = str(card.get("customer_name") or "").strip()
    text = f"{title} {customer}".casefold()
    reasons: list[str] = []
    score = 0.0

    status = str(card.get("status") or "").casefold()
    if "отмен" in status:
        return "OUT", 0.0, ["procurement_cancelled"]

    deadline = _parse_deadline(card.get("deadline"))
    if deadline is not None and deadline <= now:
        return "OUT", 0.0, ["application_deadline_expired"]

    excluded = [
        keyword for keyword in profile.exclude_keywords if keyword.casefold() in text
    ]
    if excluded:
        return "OUT", 0.0, [f"excluded_keyword:{keyword}" for keyword in excluded]

    matches = [
        keyword for keyword in profile.include_keywords if keyword.casefold() in text
    ]
    score += min(len(matches), 6) * 12.0
    if profile.require_include_keyword and profile.include_keywords and not matches:
        return "OUT", score, ["no_profile_keyword_match"]
    if matches:
        reasons.append("profile_keywords:" + ",".join(matches[:6]))

    nmck = _number(card.get("initial_price"))
    if profile.min_nmck is not None:
        if nmck is None:
            reasons.append("nmck_unknown")
            score -= 5
        elif nmck < profile.min_nmck:
            return "OUT", score, ["nmck_below_profile_minimum"]
    if profile.max_nmck is not None:
        if nmck is None:
            reasons.append("nmck_unknown")
            score -= 5
        elif nmck > profile.max_nmck:
            return "OUT", score, ["nmck_above_profile_maximum"]

    if deadline is not None:
        hours = max(0.0, (deadline - now).total_seconds() / 3600)
        if hours < 24:
            reasons.append("deadline_under_24h")
            score -= 12
        elif hours < 72:
            reasons.append("deadline_under_72h")
            score -= 4
        else:
            score += 4
    else:
        reasons.append("deadline_unknown")
        score -= 5

    if nmck is not None:
        score += 3
    return "IN", max(0.0, score), reasons


def _previous_item(
    session: Session,
    *,
    profile_id: str,
    current_run_id: str,
    registry_number: str,
) -> DailyTenderRunItem | None:
    return session.scalar(
        select(DailyTenderRunItem)
        .join(DailyTenderRun, DailyTenderRun.run_id == DailyTenderRunItem.run_id)
        .where(
            DailyTenderRun.profile_id == profile_id,
            DailyTenderRun.run_id != current_run_id,
            DailyTenderRunItem.registry_number == registry_number,
        )
        .order_by(DailyTenderRunItem.created_at.desc(), DailyTenderRunItem.id.desc())
        .limit(1)
    )


def _discover(
    session: Session,
    run: DailyTenderRun,
    profile: DailyTenderProfile,
) -> list[str]:
    today = datetime.now(UTC).date()
    date_from = (today - timedelta(days=profile.lookback_days)).isoformat()
    date_to = today.isoformat()
    discovered: dict[str, dict[str, Any]] = {}
    query_errors: list[str] = []

    for query in profile.queries:
        try:
            payload = search_public_44fz(
                query=query,
                law=profile.law,
                date_from=date_from,
                date_to=date_to,
                status_filter=profile.status_filter,
                page=1,
                page_size=profile.max_results_per_query,
                max_results=profile.max_results_per_query,
            )
        except Exception as exc:  # noqa: BLE001 - isolate one public-search failure
            query_errors.append(f"{query}: {type(exc).__name__}")
            continue
        cards = payload.get("cards") if isinstance(payload, dict) else []
        if not isinstance(cards, list):
            query_errors.append(f"{query}: invalid_search_payload")
            continue
        for card in cards:
            if not isinstance(card, dict):
                continue
            registry = _registry_number(card)
            if not registry:
                continue
            bucket = discovered.setdefault(
                registry,
                {"card": dict(card), "queries": []},
            )
            if query not in bucket["queries"]:
                bucket["queries"].append(query)
            current = bucket["card"]
            if not current.get("source_url") and card.get("source_url"):
                bucket["card"] = dict(card)

    for registry, payload in discovered.items():
        existing = session.scalar(
            select(DailyTenderRunItem).where(
                DailyTenderRunItem.run_id == run.run_id,
                DailyTenderRunItem.registry_number == registry,
            )
        )
        if existing:
            merged = list(existing.query_hits_json or [])
            for query in payload["queries"]:
                if query not in merged:
                    merged.append(query)
            existing.query_hits_json = merged
            existing.updated_at = utcnow()
            session.add(existing)
            continue

        card = payload["card"]
        fingerprint = _fingerprint(card)
        previous = _previous_item(
            session,
            profile_id=profile.profile_id,
            current_run_id=run.run_id,
            registry_number=registry,
        )
        unchanged = (
            previous is not None
            and previous.source_fingerprint == fingerprint
            and (
                previous.status in _TERMINAL_REUSE_STATUSES
                or str(previous.analysis_status or "").startswith("completed")
            )
        )
        item = DailyTenderRunItem(
            run_id=run.run_id,
            registry_number=registry,
            law=profile.law,
            source=str(card.get("source") or "public_eis_html_44fz"),
            source_url=str(card.get("source_url") or "") or None,
            title=str(card.get("title") or f"Закупка {registry}"),
            customer_name=str(card.get("customer_name") or "") or None,
            nmck_amount=_number(card.get("initial_price")),
            deadline_at=_parse_deadline(card.get("deadline")),
            source_fingerprint=fingerprint,
            query_hits_json=list(payload["queries"]),
            stage="DEDUPE" if unchanged else "SCREEN",
            status="DUPLICATE" if unchanged else "DISCOVERED",
            changed_since_previous=bool(
                previous is not None and previous.source_fingerprint != fingerprint
            ),
            screening_reasons_json=(
                [f"unchanged_from_run:{previous.run_id}"] if unchanged and previous else []
            ),
        )
        session.add(item)

    run.error_summary = "; ".join(query_errors[:10]) if query_errors else None
    run.current_stage = "SCREEN"
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    return query_errors


def _screen(session: Session, run: DailyTenderRun, profile: DailyTenderProfile) -> None:
    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(
                DailyTenderRunItem.run_id == run.run_id,
                DailyTenderRunItem.status == "DISCOVERED",
            )
            .order_by(DailyTenderRunItem.created_at.asc(), DailyTenderRunItem.id.asc())
        )
    )
    for item in items:
        status, score, reasons = _screen_card(
            profile,
            {
                "title": item.title,
                "customer_name": item.customer_name,
                "initial_price": item.nmck_amount,
                "deadline": item.deadline_at.isoformat() if item.deadline_at else None,
                "status": None,
            },
        )
        item.screening_status = status
        item.screening_score = score
        item.screening_reasons_json = reasons
        item.stage = "SCREEN"
        item.status = "SHORTLISTED" if status == "IN" else "SCREENED_OUT"
        item.updated_at = utcnow()
        session.add(item)

    # SessionLocal deliberately uses autoflush=False. Flush screening decisions
    # before querying them, otherwise the DB still sees the pre-screen
    # DISCOVERED statuses and the deep-analysis cap is silently bypassed.
    session.flush()
    run_items = list(
        session.scalars(
            select(DailyTenderRunItem).where(DailyTenderRunItem.run_id == run.run_id)
        )
    )
    reserved_ids = {
        item.id
        for item in run_items
        if item.status in {"PROCESSING", "MANAGER_READY"}
        or item.analysis_run_id is not None
    }
    available_shortlist_slots = max(
        0,
        profile.max_deep_analysis - len(reserved_ids),
    )
    shortlisted = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(
                DailyTenderRunItem.run_id == run.run_id,
                DailyTenderRunItem.status == "SHORTLISTED",
            )
            .order_by(
                DailyTenderRunItem.screening_score.desc(),
                DailyTenderRunItem.created_at.asc(),
            )
        )
    )
    for item in shortlisted[available_shortlist_slots:]:
        item.status = "SCREENED_OUT"
        item.screening_status = "OUT"
        item.screening_reasons_json = [
            *(item.screening_reasons_json or []),
            "daily_deep_analysis_limit",
        ]
        item.updated_at = utcnow()
        session.add(item)
    run.current_stage = "ACQUIRE_DOCS"
    run.updated_at = utcnow()
    session.add(run)
    session.commit()


def _ensure_canonical_intake(
    session: Session,
    *,
    run: DailyTenderRun,
    item: DailyTenderRunItem,
) -> str:
    if item.deal_id:
        return item.deal_id
    portal_url = item.source_url or (
        "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
        f"?searchString={item.registry_number}"
    )
    intake, _source = create_tender_intake(
        session,
        CreateTenderIntakeRequest(
            source_type=TenderSourceType.PORTAL,
            source_channel="daily_tender_run",
            source_title=item.title,
            source_customer_name=item.customer_name or "Не указан",
            source_procurement_number=item.registry_number,
            payload_json={
                "portal_url": portal_url,
                "registry_number": item.registry_number,
                "daily_tender_run_id": run.run_id,
                "profile_id": run.profile_id,
                "profile_version": run.profile_version,
                "nmck_amount": item.nmck_amount,
                "deadline": item.deadline_at.isoformat() if item.deadline_at else None,
                "query_hits": list(item.query_hits_json or []),
                "source_fingerprint": item.source_fingerprint,
            },
            initial_source_type=InitialSourceType.PORTAL_INGEST,
            direction_type=DirectionType.SERVICE,
            domain_type="IT_SOFTWARE_SERVICES",
        ),
    )
    item.deal_id = intake.deal_id
    item.updated_at = utcnow()
    session.add(item)
    session.commit()
    return intake.deal_id


def _set_run_stage(session: Session, run: DailyTenderRun, stage: str) -> None:
    run.current_stage = stage
    run.updated_at = utcnow()
    session.add(run)


def _process_item(
    session: Session,
    *,
    run: DailyTenderRun,
    item: DailyTenderRunItem,
    profile: DailyTenderProfile,
) -> None:
    item.status = "PROCESSING"
    item.stage = "ACQUIRE_DOCS"
    item.error = None
    item.updated_at = utcnow()
    _set_run_stage(session, run, "ACQUIRE_DOCS")
    session.add(item)
    session.commit()

    _ensure_canonical_intake(session, run=run, item=item)

    item.stage = "ACQUIRE_DOCS"
    item.updated_at = utcnow()
    _set_run_stage(session, run, "ACQUIRE_DOCS")
    session.add(item)
    session.commit()
    TenderResearchPipeline(session).ingest_public_by_registry_number(item.registry_number)

    item.stage = "INDEX_DATA_PLATFORM"
    item.updated_at = utcnow()
    _set_run_stage(session, run, "INDEX_DATA_PLATFORM")
    session.add(item)
    session.commit()
    prepared = prepare_tender_for_analysis(
        registry_number=item.registry_number,
        session=session,
    )
    if not prepared.ready_for_analysis:
        details = "; ".join(prepared.errors or prepared.warnings or ["data_platform_not_ready"])
        raise RuntimeError(f"Data Platform preparation is not ready: {details}")

    item.stage = "ANALYZE"
    item.updated_at = utcnow()
    _set_run_stage(session, run, "ANALYZE")
    session.add(item)
    session.commit()
    analysis = analyze_tender(
        registry_number=item.registry_number,
        use_llm=profile.analysis_use_llm,
        analysis_mode=profile.analysis_mode,
        session=session,
        save_report=True,
        record_history=True,
        history_source=f"daily_tender_run:{run.run_id}",
    )
    item.analysis_run_id = analysis.run_id
    item.analysis_status = analysis.status
    item.analysis_report_path = analysis.report_path
    item.updated_at = utcnow()
    session.add(item)
    session.commit()

    if not str(analysis.status).startswith("completed"):
        details = "; ".join(analysis.errors or analysis.warnings or ["deep_analysis_incomplete"])
        raise RuntimeError(f"Deep analysis did not complete: {details}")

    item.stage = "SUMMARIZE"
    item.updated_at = utcnow()
    _set_run_stage(session, run, "SUMMARIZE")
    session.add(item)
    session.commit()
    synthesis = synthesize_manager_brief(
        analysis,
        registry_number=item.registry_number,
        title=item.title,
        customer_name=item.customer_name,
        nmck_amount=item.nmck_amount,
        deadline_text=item.deadline_at.isoformat() if item.deadline_at else None,
        use_llm=profile.synthesis_use_llm,
    )
    item.agent_recommendation = synthesis.recommendation
    item.agent_confidence = synthesis.confidence
    item.agent_rationale = synthesis.rationale
    item.strongest_reasons_json = list(synthesis.strongest_reasons)
    item.blockers_json = list(synthesis.blockers)
    item.unknowns_json = list(synthesis.unknowns)
    item.synthesis_json = synthesis.model_dump(mode="json")
    item.stage = "WAIT_HUMAN"
    item.status = "MANAGER_READY"
    item.updated_at = utcnow()
    _set_run_stage(session, run, "WAIT_HUMAN")
    session.add(item)
    session.commit()


def _counts(items: list[DailyTenderRunItem]) -> dict[str, int]:
    recommendations = {"GO": 0, "NO_GO": 0, "NEEDS_REVIEW": 0}
    for item in items:
        if item.agent_recommendation in recommendations:
            recommendations[item.agent_recommendation] += 1
    return {
        "discovered": len(items),
        "duplicates": sum(item.status == "DUPLICATE" for item in items),
        "screened_out": sum(item.status == "SCREENED_OUT" for item in items),
        "deep_analyzed": sum(item.status == "MANAGER_READY" for item in items),
        "failed": sum(item.status == "FAILED" for item in items),
        "needs_manager": sum(item.status == "MANAGER_READY" for item in items),
        "agent_go": recommendations["GO"],
        "agent_no_go": recommendations["NO_GO"],
        "agent_needs_review": recommendations["NEEDS_REVIEW"],
    }


def _digest(run: DailyTenderRun, items: list[DailyTenderRunItem]) -> dict[str, Any]:
    counts = _counts(items)
    actionable = []
    for item in items:
        if item.status != "MANAGER_READY":
            continue
        actionable.append(
            {
                "deal_id": item.deal_id,
                "registry_number": item.registry_number,
                "title": item.title,
                "customer_name": item.customer_name,
                "nmck_amount": item.nmck_amount,
                "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
                "recommendation": item.agent_recommendation,
                "confidence": item.agent_confidence,
                "rationale": item.agent_rationale,
                "strongest_reasons": list(item.strongest_reasons_json or []),
                "blockers": list(item.blockers_json or []),
                "unknowns": list(item.unknowns_json or []),
                "analysis_run_id": item.analysis_run_id,
                "analysis_report_path": item.analysis_report_path,
                "human_decision": "PENDING",
            }
        )
    actionable.sort(
        key=lambda row: (
            {"GO": 0, "NEEDS_REVIEW": 1, "NO_GO": 2}.get(row["recommendation"], 3),
            row["deadline_at"] or "9999",
            row["registry_number"],
        )
    )
    return {
        "run_id": run.run_id,
        "profile_id": run.profile_id,
        "profile_version": run.profile_version,
        "counts": counts,
        "actionable": actionable,
        "human_control": {
            "decision_required": True,
            "allowed_actions": ["GO", "NO_GO", "DEFER"],
            "external_submission_allowed": False,
        },
    }


def create_daily_tender_run(
    session: Session,
    payload: StartDailyTenderRunRequest,
) -> DailyTenderRun:
    profile = load_daily_tender_profile(payload.profile_id)
    run = DailyTenderRun(
        run_id=_new_run_id(),
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_snapshot_json=profile.model_dump(mode="json"),
        status="PENDING",
        current_stage="DISCOVER",
        counts_json={},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    if payload.run_now:
        return execute_daily_tender_run(
            session,
            run.run_id,
            retry_failed=payload.retry_failed,
        )
    return run


def execute_daily_tender_run(
    session: Session,
    run_id: str,
    *,
    retry_failed: bool = False,
) -> DailyTenderRun:
    run = session.scalar(select(DailyTenderRun).where(DailyTenderRun.run_id == run_id))
    if run is None:
        raise NotFoundError(f"Daily Tender Run '{run_id}' was not found")
    profile = DailyTenderProfile.model_validate(run.profile_snapshot_json)
    if run.status == "COMPLETED" and not retry_failed:
        return run

    run.status = "RUNNING"
    run.completed_at = None
    run.updated_at = utcnow()
    session.add(run)
    session.commit()

    items = list(
        session.scalars(
            select(DailyTenderRunItem).where(DailyTenderRunItem.run_id == run.run_id)
        )
    )
    if not items:
        run.current_stage = "DISCOVER"
        session.add(run)
        session.commit()
        _discover(session, run, profile)

    _screen(session, run, profile)

    if retry_failed:
        failed = list(
            session.scalars(
                select(DailyTenderRunItem).where(
                    DailyTenderRunItem.run_id == run.run_id,
                    DailyTenderRunItem.status == "FAILED",
                )
            )
        )
        for item in failed:
            item.status = "SHORTLISTED"
            item.error = None
            item.stage = "ACQUIRE_DOCS"
            item.updated_at = utcnow()
            session.add(item)
        session.commit()

    candidates = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(
                DailyTenderRunItem.run_id == run.run_id,
                DailyTenderRunItem.status.in_(tuple(_PROCESSABLE_STATUSES)),
            )
            .order_by(
                DailyTenderRunItem.screening_score.desc(),
                DailyTenderRunItem.created_at.asc(),
            )
        )
    )
    for item in candidates:
        try:
            _process_item(session, run=run, item=item, profile=profile)
        except Exception as exc:  # noqa: BLE001 - isolate one procurement failure
            session.rollback()
            failed_item = session.get(DailyTenderRunItem, item.id)
            if failed_item is not None:
                failed_item.status = "FAILED"
                failed_item.stage = "FAILED"
                failed_item.error = f"{type(exc).__name__}: {exc}"[:4000]
                failed_item.updated_at = utcnow()
                session.add(failed_item)
                session.commit()

    items = list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(DailyTenderRunItem.run_id == run.run_id)
            .order_by(DailyTenderRunItem.created_at.asc(), DailyTenderRunItem.id.asc())
        )
    )
    run = session.scalar(select(DailyTenderRun).where(DailyTenderRun.run_id == run_id))
    if run is None:
        raise NotFoundError(f"Daily Tender Run '{run_id}' was not found")
    run.counts_json = _counts(items)
    run.digest_json = _digest(run, items)
    if run.counts_json["needs_manager"]:
        run.current_stage = "WAIT_HUMAN"
        run.status = "WAITING_HUMAN"
    elif run.counts_json["failed"]:
        run.current_stage = "DONE"
        run.status = "COMPLETED_WITH_ERRORS"
    else:
        run.current_stage = "DONE"
        run.status = "COMPLETED"
    run.completed_at = utcnow()
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_daily_tender_run(session: Session, run_id: str) -> DailyTenderRun:
    run = session.scalar(select(DailyTenderRun).where(DailyTenderRun.run_id == run_id))
    if run is None:
        raise NotFoundError(f"Daily Tender Run '{run_id}' was not found")
    return run


def get_latest_daily_tender_run(
    session: Session,
    *,
    profile_id: str | None = None,
) -> DailyTenderRun | None:
    query = select(DailyTenderRun)
    if profile_id:
        query = query.where(DailyTenderRun.profile_id == profile_id)
    return session.scalar(
        query.order_by(DailyTenderRun.created_at.desc(), DailyTenderRun.id.desc()).limit(1)
    )


def list_daily_tender_run_items(
    session: Session,
    run_id: str,
) -> list[DailyTenderRunItem]:
    return list(
        session.scalars(
            select(DailyTenderRunItem)
            .where(DailyTenderRunItem.run_id == run_id)
            .order_by(
                DailyTenderRunItem.screening_score.desc(),
                DailyTenderRunItem.created_at.asc(),
            )
        )
    )


def to_run_response(session: Session, run: DailyTenderRun) -> DailyTenderRunResponse:
    items = list_daily_tender_run_items(session, run.run_id)
    return DailyTenderRunResponse(
        run_id=run.run_id,
        profile_id=run.profile_id,
        profile_version=run.profile_version,
        status=run.status,
        current_stage=run.current_stage,
        counts=dict(run.counts_json or {}),
        digest=run.digest_json,
        error_summary=run.error_summary,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        items=[
            DailyTenderRunItemResponse(
                registry_number=item.registry_number,
                law=item.law,
                source=item.source,
                source_url=item.source_url,
                title=item.title,
                customer_name=item.customer_name,
                nmck_amount=item.nmck_amount,
                deadline_at=item.deadline_at,
                query_hits=list(item.query_hits_json or []),
                stage=item.stage,
                status=item.status,
                screening_status=item.screening_status,
                screening_score=item.screening_score,
                screening_reasons=list(item.screening_reasons_json or []),
                changed_since_previous=item.changed_since_previous,
                deal_id=item.deal_id,
                analysis_run_id=item.analysis_run_id,
                analysis_status=item.analysis_status,
                analysis_report_path=item.analysis_report_path,
                agent_recommendation=item.agent_recommendation,
                agent_confidence=item.agent_confidence,
                agent_rationale=item.agent_rationale,
                strongest_reasons=list(item.strongest_reasons_json or []),
                blockers=list(item.blockers_json or []),
                unknowns=list(item.unknowns_json or []),
                error=item.error,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )
