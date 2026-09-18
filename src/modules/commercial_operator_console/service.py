import html

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.modules.commercial_operator_console.schemas import (
    CommercialOperatorActionRequest,
    CommercialOperatorActionResponse,
    KanbanStatusTransitionRequest,
)
from src.modules.contract_risks.models import (
    ContractRiskFlag,
    ContractRiskRecord,
    ContractRiskSet,
)
from src.modules.deal_registry.models import Deal
from src.modules.document_requirements.models import (
    DocumentRequirementRow,
    DocumentRequirementSet,
)
from src.modules.event_log.models import DecisionRecord
from src.modules.event_log.schemas import AppendDecisionRequest, AppendEventRequest
from src.modules.event_log.service import append_decision, append_event
from src.modules.initial_tech_risks.models import (
    InitialTechRiskFlag,
    InitialTechRiskFlagSet,
)
from src.modules.prompt_schema_library.models import PromptSchemaRecord
from src.modules.requirement_extraction.models import (
    RequirementExtractionRecord,
    RequirementExtractionSet,
)
from src.modules.runtime_control_traces.models import RuntimeControlTrace
from src.modules.status_engine.models import DealStatusHistory
from src.modules.status_engine.schemas import ApplyTransitionRequest
from src.modules.status_engine.service import apply_transition
from src.modules.tender_summary.models import TenderSummary
from src.shared.enums import ChangedByType, DealStatus, DecisionByType, EventSeverity
from src.shared.errors import NotFoundError


def _latest(session: Session, model, *conditions):
    return session.scalar(select(model).where(*conditions).order_by(model.created_at.desc(), model.id.desc()).limit(1))


def _load_deal(session: Session, deal_id: str) -> Deal:
    deal = session.scalar(select(Deal).where(Deal.deal_id == deal_id, Deal.is_deleted.is_(False)))
    if not deal:
        raise NotFoundError(f"Deal '{deal_id}' was not found")
    return deal


def _load_snapshot(session: Session, deal_id: str) -> dict:
    deal = _load_deal(session, deal_id)
    summary = _latest(session, TenderSummary, TenderSummary.deal_id == deal_id)
    req_set = _latest(session, RequirementExtractionSet, RequirementExtractionSet.document_set_id == summary.document_set_id) if summary else None
    req_records = (
        list(
            session.scalars(
                select(RequirementExtractionRecord)
                .where(RequirementExtractionRecord.requirement_extraction_set_id == req_set.requirement_extraction_set_id)
                .order_by(RequirementExtractionRecord.created_at.asc(), RequirementExtractionRecord.id.asc())
            )
        )
        if req_set
        else []
    )
    doc_req_set = _latest(session, DocumentRequirementSet, DocumentRequirementSet.deal_id == deal_id)
    doc_req_rows = (
        list(
            session.scalars(
                select(DocumentRequirementRow)
                .where(DocumentRequirementRow.document_requirement_set_id == doc_req_set.document_requirement_set_id)
                .order_by(DocumentRequirementRow.sequence_no.asc(), DocumentRequirementRow.id.asc())
            )
        )
        if doc_req_set
        else []
    )
    tech_risk_set = _latest(session, InitialTechRiskFlagSet, InitialTechRiskFlagSet.deal_id == deal_id)
    tech_risk_rows = (
        list(
            session.scalars(
                select(InitialTechRiskFlag)
                .where(InitialTechRiskFlag.risk_flag_set_id == tech_risk_set.risk_flag_set_id)
                .order_by(InitialTechRiskFlag.created_at.asc(), InitialTechRiskFlag.id.asc())
            )
        )
        if tech_risk_set
        else []
    )
    contract_risk_set = _latest(session, ContractRiskSet, ContractRiskSet.deal_id == deal_id)
    contract_risk_rows = []
    if contract_risk_set:
        for record in session.scalars(
            select(ContractRiskRecord)
            .where(ContractRiskRecord.contract_risk_set_id == contract_risk_set.contract_risk_set_id)
            .order_by(ContractRiskRecord.created_at.asc(), ContractRiskRecord.id.asc())
        ):
            flags = list(
                session.scalars(
                    select(ContractRiskFlag)
                    .where(ContractRiskFlag.contract_risk_id == record.contract_risk_id)
                    .order_by(ContractRiskFlag.created_at.asc(), ContractRiskFlag.id.asc())
                )
            )
            contract_risk_rows.append((record, flags))
    traces = list(
        session.scalars(
            select(RuntimeControlTrace)
            .where(RuntimeControlTrace.target_record_id == deal_id)
            .order_by(RuntimeControlTrace.created_at.desc(), RuntimeControlTrace.id.desc())
        )
    )
    prompt_labels = {
        item.prompt_schema_id: item.asset_key
        for item in session.scalars(select(PromptSchemaRecord).where(PromptSchemaRecord.prompt_schema_id.in_([trace.prompt_schema_ref for trace in traces if trace.prompt_schema_ref])))
    } if traces else {}
    decisions = list(
        session.scalars(
            select(DecisionRecord).where(DecisionRecord.deal_id == deal_id).order_by(DecisionRecord.created_at.desc(), DecisionRecord.id.desc())
        )
    )
    return {
        "deal": deal,
        "summary": summary,
        "requirement_records": req_records,
        "document_requirements": doc_req_rows,
        "tech_risks": tech_risk_rows,
        "contract_risks": contract_risk_rows,
        "traces": traces,
        "prompt_labels": prompt_labels,
        "decisions": decisions,
    }


def _layout(title: str, body: str) -> str:
    return (
        "<html><head><title>"
        + html.escape(title)
        + "</title><style>body{font-family:Arial,sans-serif;max-width:1400px;margin:40px auto;padding:0 16px;line-height:1.5}"
        + "nav a{margin-right:12px}code{background:#f4f4f4;padding:2px 4px}"
        + ".kanban-board{display:flex;gap:12px;overflow-x:auto;align-items:flex-start;padding-bottom:12px}"
        + ".kanban-column{min-width:260px;max-width:260px;background:#f6f7f8;border:1px solid #ddd;border-radius:8px;padding:10px}"
        + ".kanban-column h2{font-size:14px;margin:0 0 10px}.count{font-weight:normal;color:#666}"
        + ".kanban-card{background:white;border:1px solid #ddd;border-radius:6px;padding:10px;margin-bottom:8px}"
        + ".kanban-card h3{font-size:15px;margin:0 0 8px}.kanban-card p{font-size:13px;margin:0 0 6px}"
        + ".filters{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:16px 0}"
        + ".filters label{display:flex;flex-direction:column;font-size:12px}.warning{padding:10px;border:1px solid #b7791f;margin:12px 0}"
        + ".empty{color:#777;font-size:13px}</style></head><body>"
        + body
        + "</body></html>"
    )


def render_dashboard_html(session: Session) -> str:
    deals = list(session.scalars(select(Deal).where(Deal.is_deleted.is_(False)).order_by(Deal.created_at.desc(), Deal.id.desc()).limit(20)))
    rows = "".join(
        f"<li><a href='/commercial-console/deals/{html.escape(deal.deal_id)}'>{html.escape(deal.title)}</a> "
        f"({html.escape(deal.deal_id)} / {html.escape(str(deal.current_status))})</li>"
        for deal in deals
    ) or "<li>No deals available.</li>"
    return _layout(
        "Commercial Operator Dashboard",
        "<h1>Commercial Operator Dashboard</h1><p>Internal-only commercial MVP review surface.</p><ul>" + rows + "</ul>",
    )



def _kanban_deals(
    session: Session,
    *,
    status_filter: DealStatus | None = None,
    priority_bucket: str | None = None,
    customer_name: str | None = None,
    procurement_number: str | None = None,
    search: str | None = None,
) -> list[Deal]:
    query = select(Deal).where(
        Deal.is_deleted.is_(False),
        Deal.archived_at.is_(None),
    )
    if status_filter is not None:
        query = query.where(Deal.current_status == status_filter)
    if priority_bucket:
        query = query.where(Deal.priority_bucket == priority_bucket.strip())
    if customer_name:
        query = query.where(Deal.customer_name.ilike(f"%{customer_name.strip()}%"))
    if procurement_number:
        query = query.where(Deal.procurement_number == procurement_number.strip())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Deal.title.ilike(term),
                Deal.customer_name.ilike(term),
                Deal.procurement_number.ilike(term),
            )
        )
    query = query.order_by(Deal.created_at.desc(), Deal.id.desc())
    return list(session.scalars(query))


def _kanban_card(deal: Deal) -> str:
    customer = html.escape(deal.customer_name or "—")
    procurement = html.escape(deal.procurement_number or "—")
    priority = html.escape(deal.priority_bucket or "—")
    deal_id = html.escape(deal.deal_id)
    return (
        "<article class='kanban-card'>"
        f"<h3><a href='/commercial-console/deals/{deal_id}'>{html.escape(deal.title)}</a></h3>"
        f"<p><strong>Procurement:</strong> {procurement}<br>"
        f"<strong>Customer:</strong> {customer}<br>"
        f"<strong>Priority:</strong> {priority}</p>"
        f"<small>{deal_id}</small>"
        "</article>"
    )


def render_kanban_html(
    session: Session,
    *,
    status_filter: DealStatus | None = None,
    priority_bucket: str | None = None,
    customer_name: str | None = None,
    procurement_number: str | None = None,
    search: str | None = None,
) -> str:
    deals = _kanban_deals(
        session,
        status_filter=status_filter,
        priority_bucket=priority_bucket,
        customer_name=customer_name,
        procurement_number=procurement_number,
        search=search,
    )
    grouped: dict[DealStatus, list[Deal]] = {status: [] for status in DealStatus}
    invalid_status_deals: list[Deal] = []
    for deal in deals:
        try:
            grouped[DealStatus(deal.current_status)].append(deal)
        except ValueError:
            invalid_status_deals.append(deal)

    columns = "".join(
        (
            f"<section class='kanban-column' data-status='{html.escape(status.value)}'>"
            f"<h2>{html.escape(status.value)} <span class='count'>{len(grouped[status])}</span></h2>"
            + ("".join(_kanban_card(deal) for deal in grouped[status]) or "<p class='empty'>No deals.</p>")
            + "</section>"
        )
        for status in DealStatus
        if status_filter is None or status == status_filter
    )
    integrity_warning = ""
    if invalid_status_deals:
        integrity_warning = (
            "<aside class='warning'><strong>Data integrity warning:</strong> "
            f"{len(invalid_status_deals)} active deal(s) have a non-canonical status and are not placed on the board."
            "</aside>"
        )

    def _filter_value(value: str | None) -> str:
        return html.escape(value or "", quote=True)

    selected_status = status_filter.value if status_filter else ""
    status_options = ["<option value=''>All statuses</option>"]
    for status in DealStatus:
        selected = " selected" if status.value == selected_status else ""
        status_options.append(
            f"<option value='{html.escape(status.value)}'{selected}>{html.escape(status.value)}</option>"
        )
    filters = (
        "<form method='get' action='/commercial-console/kanban' class='filters'>"
        "<label>Status <select name='status'>"
        + "".join(status_options)
        + "</select></label>"
        f"<label>Priority <input name='priority_bucket' value='{_filter_value(priority_bucket)}'></label>"
        f"<label>Customer <input name='customer_name' value='{_filter_value(customer_name)}'></label>"
        f"<label>Procurement <input name='procurement_number' value='{_filter_value(procurement_number)}'></label>"
        f"<label>Search <input name='q' value='{_filter_value(search)}'></label>"
        "<button type='submit'>Filter</button>"
        "<a href='/commercial-console/kanban'>Reset</a>"
        "</form>"
    )
    return _layout(
        "Procurement Kanban",
        "<nav><a href='/commercial-console'>dashboard</a> <a href='/commercial-console/kanban'>kanban</a></nav>"
        "<h1>Procurement Kanban</h1>"
        "<p>Internal board over the canonical deal status engine. Archived and deleted deals are excluded.</p>"
        + filters
        + integrity_warning
        + "<div class='kanban-board'>"
        + columns
        + "</div>",
    )


def apply_kanban_status_transition(
    session: Session,
    deal_id: str,
    payload: KanbanStatusTransitionRequest,
) -> DealStatusHistory:
    _load_deal(session, deal_id)
    return apply_transition(
        session,
        ApplyTransitionRequest(
            deal_id=deal_id,
            to_status=payload.to_status,
            changed_by_type=ChangedByType.HUMAN,
            changed_by_ref=payload.operator_ref,
            reason_code="commercial_console_kanban",
            reason_text=payload.reason,
            is_override=False,
        ),
    )

def render_tender_card_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    deal = snapshot["deal"]
    summary = snapshot["summary"]
    nav = _deal_nav(deal_id)
    summary_text = html.escape(summary.summary_text) if summary else "No summary available."
    body = (
        nav
        + f"<h1>{html.escape(deal.title)}</h1>"
        + f"<p><strong>Deal:</strong> {html.escape(deal.deal_id)}<br>"
        + f"<strong>Customer:</strong> {html.escape(deal.customer_name or '')}<br>"
        + f"<strong>Procurement:</strong> {html.escape(deal.procurement_number or '')}<br>"
        + f"<strong>Status:</strong> {html.escape(str(deal.current_status))}</p>"
        + f"<h2>Tender Card</h2><p>{summary_text}</p>"
    )
    return _layout("Commercial Tender Card", body)


def render_report_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    nav = _deal_nav(deal_id)
    requirements = "".join(f"<li>{html.escape(row.requirement_title)}</li>" for row in snapshot["document_requirements"]) or "<li>No requirements.</li>"
    decisions = "".join(
        f"<li><code>{html.escape(item.decision_code)}</code> by {html.escape(item.decided_by_ref or 'n/a')} - {html.escape(item.rationale or '')}</li>"
        for item in snapshot["decisions"][:5]
    ) or "<li>No decisions.</li>"
    body = (
        nav
        + "<h1>Pre-Bid Report View</h1>"
        + f"<p>{html.escape(snapshot['summary'].summary_text if snapshot['summary'] else 'No summary available.')}</p>"
        + "<h2>Requirements Snapshot</h2><ul>"
        + requirements
        + "</ul><h2>Recent Decisions</h2><ul>"
        + decisions
        + "</ul>"
    )
    return _layout("Commercial Pre-Bid Report", body)


def render_requirements_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    nav = _deal_nav(deal_id)
    extracted = "".join(
        f"<li>{html.escape(item.requirement_code)}: {html.escape(item.requirement_text)}</li>"
        for item in snapshot["requirement_records"]
    ) or "<li>No extracted requirements.</li>"
    formal = "".join(
        f"<li>{html.escape(item.row_code)}: {html.escape(item.requirement_title)} "
        f"(manual_review={html.escape(str(item.requires_manual_review))})</li>"
        for item in snapshot["document_requirements"]
    ) or "<li>No formal document requirements.</li>"
    return _layout(
        "Commercial Requirements View",
        nav + "<h1>Requirements</h1><h2>Extracted</h2><ul>" + extracted + "</ul><h2>Formal</h2><ul>" + formal + "</ul>",
    )


def render_risks_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    nav = _deal_nav(deal_id)
    tech = "".join(
        f"<li>[{html.escape(str(item.severity))}] {html.escape(item.summary)}</li>"
        for item in snapshot["tech_risks"]
    ) or "<li>No technical risks.</li>"
    contract = "".join(
        f"<li>[{html.escape(str(record.severity))}] {html.escape(record.summary)}</li>"
        for record, _flags in snapshot["contract_risks"]
    ) or "<li>No contract risks.</li>"
    return _layout(
        "Commercial Risks View",
        nav + "<h1>Risks</h1><h2>Technical</h2><ul>" + tech + "</ul><h2>Contract</h2><ul>" + contract + "</ul>",
    )


def render_runtime_traces_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    nav = _deal_nav(deal_id)
    traces = "".join(
        f"<li><code>{html.escape(trace.runtime_trace_id)}</code> "
        f"{html.escape(snapshot['prompt_labels'].get(trace.prompt_schema_ref, trace.prompt_schema_ref or 'no-prompt'))} "
        f"validation={html.escape(str(trace.validation_status))} review={html.escape(str(trace.human_review_status))}</li>"
        for trace in snapshot["traces"]
    ) or "<li>No runtime traces.</li>"
    return _layout(
        "Commercial Runtime Traces",
        nav + "<h1>Runtime Trace Review</h1><ul>" + traces + "</ul>",
    )


def render_decision_html(session: Session, deal_id: str) -> str:
    snapshot = _load_snapshot(session, deal_id)
    nav = _deal_nav(deal_id)
    actions = "".join(
        f"<li><code>{html.escape(item.decision_code)}</code> - {html.escape(item.rationale or '')}</li>"
        for item in snapshot["decisions"][:10]
    ) or "<li>No recorded operator decisions.</li>"
    return _layout(
        "Commercial Decision View",
        nav
        + "<h1>Decision Action View</h1>"
        + "<p>Available actions via POST <code>/commercial-console/deals/{deal_id}/actions</code>: "
        + "<code>rejected</code>, <code>needs_more_review</code>, <code>collect_tkp</code>, <code>prepare_bid_draft</code>.</p>"
        + "<ul>"
        + actions
        + "</ul>",
    )


def _deal_nav(deal_id: str) -> str:
    return (
        "<nav>"
        f"<a href='/commercial-console'>dashboard</a>"
        f"<a href='/commercial-console/kanban'>kanban</a>"
        f"<a href='/commercial-console/deals/{deal_id}'>tender card</a>"
        f"<a href='/commercial-console/deals/{deal_id}/report'>report</a>"
        f"<a href='/commercial-console/deals/{deal_id}/requirements'>requirements</a>"
        f"<a href='/commercial-console/deals/{deal_id}/risks'>risks</a>"
        f"<a href='/commercial-console/deals/{deal_id}/runtime-traces'>runtime traces</a>"
        f"<a href='/commercial-console/deals/{deal_id}/decision'>decision</a>"
        "</nav>"
    )


def record_operator_action(
    session: Session,
    deal_id: str,
    payload: CommercialOperatorActionRequest,
) -> CommercialOperatorActionResponse:
    _load_deal(session, deal_id)
    mapping = {
        "rejected": "OPERATOR_REJECTED_PREBID",
        "needs_more_review": "OPERATOR_MARKED_NEEDS_MORE_REVIEW",
        "collect_tkp": "OPERATOR_MARKED_COLLECT_TKP",
        "prepare_bid_draft": "OPERATOR_MARKED_PREPARE_BID_DRAFT",
    }
    decision = append_decision(
        session,
        AppendDecisionRequest(
            deal_id=deal_id,
            decision_code=mapping[payload.action],
            decided_by_type=DecisionByType.HUMAN,
            decided_by_ref=payload.operator_ref,
            rationale=payload.rationale,
            payload_json={"action": payload.action, "human_control_policy": "respected"},
        ),
    )
    event = append_event(
        session,
        AppendEventRequest(
            deal_id=deal_id,
            event_code="commercial_operator_action_recorded",
            source_module_id="C4",
            severity=EventSeverity.INFO,
            payload_json={
                "decision_id": decision.decision_id,
                "action": payload.action,
                "operator_ref": payload.operator_ref,
            },
        ),
    )
    return CommercialOperatorActionResponse(
        deal_id=deal_id,
        action=payload.action,
        decision_id=decision.decision_id,
        recorded_event_id=event.event_id,
    )
