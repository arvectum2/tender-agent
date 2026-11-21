"""Human-attested progress on an owned case; not an ETP executor."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from src.modules.customer_pilot.models import PilotProject, ProcurementCase
from src.modules.saas_foundation import company_portfolio as portfolio
from src.modules.saas_foundation.commercial_capture import _authorized
from src.modules.saas_foundation.models import (
    CompanyCaseLifecycleEvent,
    CompanyPortfolioDecision,
    SaasMember,
)
from src.modules.saas_foundation.service import (
    audit,
    legal_required,
    now_utc,
    role_required,
)

Stage = Literal['PREPARING','BLOCKED','READY','SUBMITTED','WON','LOST','REJECTED','WITHDRAWN','CANCELLED']
PRE = {'PREPARING','BLOCKED','READY'}
OUTCOMES = {'WON','LOST','REJECTED','WITHDRAWN','CANCELLED'}
MAX_REVISIONS = 50


class LifecycleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stage: Stage
    expected_revision: int = Field(ge=0, le=MAX_REVISIONS)
    expected_decision_revision: int = Field(ge=1)
    rationale: str = Field(min_length=1,max_length=2000)
    source_ref: str | None = Field(default=None,max_length=500)
    occurred_at: datetime | None = None
    correct_outcome: bool = False
    idempotency_key: str = Field(min_length=8,max_length=128)

    @model_validator(mode='after')
    def validate_input(self):
        self.rationale = self.rationale.strip()
        self.source_ref = self.source_ref.strip() if self.source_ref else None
        if not self.rationale:
            raise ValueError('Rationale required')
        if self.stage not in PRE:
            if not self.source_ref or self.occurred_at is None or self.occurred_at.utcoffset() is None:
                raise ValueError('External receipt/protocol reference and aware occurrence time required')
            self.occurred_at = self.occurred_at.astimezone(UTC)
        elif self.occurred_at is not None:
            raise ValueError('Readiness recorded at server time')
        if self.correct_outcome and self.stage not in OUTCOMES:
            raise ValueError('Only terminal outcomes may be corrected')
        return self


def _events(principal,case_id):
    return select(CompanyCaseLifecycleEvent).where(CompanyCaseLifecycleEvent.tenant_id==principal.tenant_id,CompanyCaseLifecycleEvent.case_id==case_id)


def _latest(session,principal,case_id):
    return session.scalar(_events(principal,case_id).order_by(CompanyCaseLifecycleEvent.revision.desc()).limit(1))


def _view(row,decision):
    return {'event_id':row.id,'case_id':row.case_id,'revision':row.revision,'stage':row.stage,
            'go_decision_id':row.go_decision_id,'member_id':row.member_id,'created_at':portfolio._utc(row.created_at),
            'attestation':row.event_json,'readiness_stale':row.stage in PRE and (decision is None or decision.action!='GO' or decision.id!=row.go_decision_id),
            'origin':'HUMAN_ATTESTATION','external_fact_verified':False,'external_submission_allowed':False}


def state(session,principal,case_id):
    legal_required(session,principal);portfolio._owned_case(session,principal,case_id)
    latest=_latest(session,principal,case_id);decision=portfolio._latest(session,principal,case_id)
    return {'customer_id':principal.customer_id,'case_id':case_id,'decision_revision':decision.revision if decision else 0,
            'decision_action':decision.action if decision else None,'revision':latest.revision if latest else 0,
            'latest':_view(latest,decision) if latest else None,'external_submission_allowed':False}


def history(session,principal,case_id,offset=0,limit=50):
    legal_required(session,principal);portfolio._owned_case(session,principal,case_id)
    decision=portfolio._latest(session,principal,case_id)
    rows=list(session.scalars(_events(principal,case_id).order_by(CompanyCaseLifecycleEvent.revision.desc()).offset(offset).limit(limit+1)))
    return {'customer_id':principal.customer_id,'case_id':case_id,'items':[_view(row,decision) for row in rows[:limit]],'has_more':len(rows)>limit,'external_submission_allowed':False}


def record(session,principal,case_id,payload,*,require_commercial_readiness=False):
    role_required(principal,'owner','admin');legal_required(session,principal)
    # Serialize with the existing decision writer on this same case row.
    case=portfolio._owned_case(session,principal,case_id,lock=True)
    _authorized(session,principal)
    member=session.get(SaasMember,principal.member_id,populate_existing=True)
    if not member or not member.active or member.tenant_id!=principal.tenant_id or member.role not in {'owner','admin'}:
        raise HTTPException(403,'Current manager permission required')
    decision=portfolio._latest(session,principal,case_id)
    body=payload.model_dump(mode='json')
    prior=session.scalar(_events(principal,case_id).where(CompanyCaseLifecycleEvent.idempotency_key==payload.idempotency_key))
    if prior:
        if prior.member_id!=principal.member_id or prior.event_json!=body:raise HTTPException(409,'Conflicting lifecycle replay')
        return _view(prior,decision)
    latest=_latest(session,principal,case_id);revision=latest.revision if latest else 0
    if revision!=payload.expected_revision or not decision or decision.revision!=payload.expected_decision_revision:
        raise HTTPException(409,'Case decision or lifecycle changed; refresh')
    if revision>=MAX_REVISIONS:raise HTTPException(429,'Lifecycle history limit reached')
    if payload.occurred_at and payload.occurred_at>now_utc():raise HTTPException(422,'Future external occurrence not allowed')
    before=latest.stage if latest else None
    if payload.stage in PRE or payload.stage=='SUBMITTED':
        if decision.action!='GO' or (before is not None and before not in PRE):raise HTTPException(409,'Current GO and pre-submission state required')
        if payload.stage=='SUBMITTED' and (before!='READY' or latest.go_decision_id!=decision.id):raise HTTPException(409,'Current GO readiness assertion required')
        if payload.stage=='SUBMITTED' and require_commercial_readiness and portfolio._view(session,principal,case)['source_kind']=='commercial_reference':
            from src.modules.saas_foundation.company_readiness import require_current
            require_current(session,principal,case_id)
        binding=decision.id
    else:
        if before!='SUBMITTED' and not (payload.correct_outcome and before in OUTCOMES and before!=payload.stage):raise HTTPException(409,'Recorded submission or explicit terminal correction required')
        if payload.correct_outcome and before not in OUTCOMES:raise HTTPException(409,'No terminal outcome to correct')
        submitted=session.scalar(_events(principal,case_id).where(CompanyCaseLifecycleEvent.stage=='SUBMITTED').limit(1))
        if not submitted or payload.occurred_at<datetime.fromisoformat(submitted.event_json['occurred_at']):raise HTTPException(422,'Outcome cannot precede recorded submission')
        binding=submitted.go_decision_id
    row=CompanyCaseLifecycleEvent(case_id=case_id,tenant_id=principal.tenant_id,member_id=principal.member_id,go_decision_id=binding,revision=revision+1,stage=payload.stage,event_json=body,idempotency_key=payload.idempotency_key)
    session.add(row);session.flush();audit(session,principal.tenant_id,'company_case_lifecycle_recorded',principal.member_id,detail=row.id);session.commit()
    return _view(row,decision)


def metrics(session,principal):
    legal_required(session,principal)
    as_of=now_utc()
    decision=aliased(CompanyPortfolioDecision);event=aliased(CompanyCaseLifecycleEvent)
    ever_go=(select(decision.case_id).where(decision.case_id==ProcurementCase.id,decision.tenant_id==principal.tenant_id,decision.action=='GO').correlate(ProcurementCase).exists())
    latest_id=select(event.id).where(event.case_id==ProcurementCase.id,event.tenant_id==principal.tenant_id).order_by(event.revision.desc()).limit(1).correlate(ProcurementCase).scalar_subquery()
    row=aliased(CompanyCaseLifecycleEvent)
    base=select(ProcurementCase).join(PilotProject,PilotProject.id==ProcurementCase.project_id).where(ProcurementCase.customer_id==principal.customer_id,PilotProject.customer_id==principal.customer_id,PilotProject.internal_slug.in_(portfolio._PROJECT_SLUGS))
    query=base.outerjoin(row,row.id==latest_id).with_only_columns(ever_go.label('ever_go'),row.stage,func.count()).group_by(ever_go,row.stage)
    groups=session.execute(query).all()
    stages=dict.fromkeys(sorted(PRE|OUTCOMES|{'SUBMITTED','UNRECORDED'}),0);go_cases=0
    for go,stage,count in groups:
        stages[stage or 'UNRECORDED']+=count
        go_cases+=count if go else 0
    submitted=sum(stages[k] for k in OUTCOMES|{'SUBMITTED'});decided=sum(stages[k] for k in ('WON','LOST','REJECTED'))
    return {'customer_id':principal.customer_id,'as_of':as_of,'scope':'ALL_TIME_SAVED_CASES_HUMAN_ATTESTATIONS','saved_cases':sum(stages.values()),'ever_go_cases':go_cases,'recorded_submissions':submitted,'stage_counts':stages,
            'go_to_submission':{'numerator':submitted,'denominator':go_cases,'rate':submitted/go_cases if go_cases else None},
            'win_rate':{'numerator':stages['WON'],'denominator':decided,'rate':stages['WON']/decided if decided else None},
            'excluded_from_win_rate':['SUBMITTED','WITHDRAWN','CANCELLED'],'external_facts_verified':False,'market_coverage_complete':False,'contract_revenue_verified':False}
