"""Synthetic retention planning, not an authorization or deletion workflow."""
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from src.modules.saas_foundation.models import PrivateReviewRetentionProposal
from src.modules.saas_foundation.private_review_retention import (
    ScheduleProposal,
    describe,
    latest_proposal,
)
from src.shared.config.settings import invalidate_settings_cache

AS_OF = date(2026,11,19)
BASE = {'order_ref':'fixture-order','policy_ref':'fixture-policy','working_days':30,'backup_days':90}


def proposal(**changes):
    return ScheduleProposal(**(BASE | changes))


def test_unknown_and_future_dates_never_establish_deadlines():
    for p,expected in [(proposal(),'ORDER_END_UNKNOWN'),(proposal(
            order_ended_on=date(2026,11,20),end_evidence_ref='fixture-end'),'ORDER_END_IN_FUTURE')]:
        result=describe(p,as_of=AS_OF)
        assert result['proposed_working_until'] is None
        assert result['proposed_backup_until'] is None
        assert expected in result['blocking_reasons']
        assert 'HOLD_STATE_UNKNOWN' in result['blocking_reasons']
        assert result['deletion_authorized'] is False


@pytest.mark.parametrize('hold',['ACTIVE','CLEAR'])
def test_calendar_horizons_and_hold_due_never_authorize(hold):
    p=proposal(order_ended_on=date(2026,10,1),end_evidence_ref='fixture-end',
               hold_state=hold,hold_evidence_ref='fixture-hold',hold_review_on=AS_OF)
    result=describe(p,as_of=AS_OF)
    assert result['proposed_working_until']=='2026-10-31'
    assert result['proposed_backup_until']=='2026-12-30'
    assert 'HOLD_REVIEW_DUE' in result['blocking_reasons']
    assert ('HOLD_ACTIVE' in result['blocking_reasons'])==(hold=='ACTIVE')
    assert 'POLICY_APPROVAL_UNVERIFIED' in result['blocking_reasons']
    assert 'DOCUMENT_ORDER_BINDING_UNVERIFIED' in result['blocking_reasons']
    assert result['deletion_authorized'] is result['access_change_authorized'] is False
    assert 'fixture-hold' not in str(result)


@pytest.mark.parametrize('bad',[
    {'order_ended_on':AS_OF},{'end_evidence_ref':'fixture-end'},
    {'hold_state':'CLEAR'},{'hold_state':'ACTIVE','hold_evidence_ref':'fixture-hold'},
    {'hold_evidence_ref':'fixture-hold'},{'backup_days':29},
    {'working_days':True},{'working_days':-1},{'policy_ref':'with spaces'},
    {'order_ended_on':date.max,'end_evidence_ref':'fixture-end'},
    {'deletion_authorized':True},
])
def test_invalid_proposals_rejected(bad):
    with pytest.raises(ValidationError):
        proposal(**bad)


def test_migration_scoped_revision_history_and_rollback_guard(tmp_path,monkeypatch):
    path='sqlite:///'+str(tmp_path/'retention.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL',path)
    invalidate_settings_cache()
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    engine=create_engine(path)
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE saas_tenants (tenant_id VARCHAR PRIMARY KEY)'))
            conn.execute(text("INSERT INTO saas_tenants VALUES ('a'),('b')"))
        command.stamp(cfg,'124_original_form_review')
        command.upgrade(cfg,'125_private_review_retention')
        assert 'private_review_retention_proposals' in inspect(engine).get_table_names()
        command.downgrade(cfg,'124_original_form_review')
        command.upgrade(cfg,'125_private_review_retention')
        with Session(engine) as session:
            for tenant,rev in [('a',1),('a',2),('b',1)]:
                session.add(PrivateReviewRetentionProposal(tenant_id=tenant,revision=rev,**proposal().model_dump()))
            session.commit()
            assert latest_proposal(session,tenant_id='a',order_ref='fixture-order').revision==2
            assert latest_proposal(session,tenant_id='b',order_ref='fixture-order').revision==1
            assert latest_proposal(session,tenant_id='c',order_ref='fixture-order') is None
            assert latest_proposal(session,tenant_id='a',order_ref='missing') is None
            session.add(PrivateReviewRetentionProposal(tenant_id='a',revision=2,**proposal().model_dump()))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
            row=latest_proposal(session,tenant_id='a',order_ref='fixture-order')
            row.working_days=31
            with pytest.raises(ValueError,match='immutable'):
                session.commit()
            session.rollback()
            session.delete(latest_proposal(session,tenant_id='a',order_ref='fixture-order'))
            with pytest.raises(ValueError,match='immutable'):
                session.commit()
            session.rollback()
        with pytest.raises(RuntimeError,match='Cannot discard retention proposal history'):
            command.downgrade(cfg,'124_original_form_review')
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM private_review_retention_proposals'))==3
    finally:
        engine.dispose()
        invalidate_settings_cache()
