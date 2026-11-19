"""Synthetic accounting and proposed link migration tests."""
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from src.modules.saas_foundation.models import (
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
)
from src.modules.saas_foundation.private_review_retention import (
    ScheduleProposal,
    storage_summary,
)
from src.shared.config.settings import invalidate_settings_cache

NOW = datetime(2026, 11, 19, tzinfo=UTC)


def test_migrated_accounting_and_links(tmp_path, monkeypatch):
    db = 'sqlite:///'+str(tmp_path/'accounting.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL', db)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    engine = create_engine(db)

    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    try:
        with engine.begin() as conn:
            for table, key in (('saas_tenants','tenant_id'),('saas_members','id'),('saas_runs','run_id')):
                conn.exec_driver_sql(f'CREATE TABLE {table} ({key} VARCHAR PRIMARY KEY)')
            conn.exec_driver_sql("INSERT INTO saas_tenants VALUES ('a'),('b')")
            conn.exec_driver_sql("INSERT INTO saas_members VALUES ('creator'),('reviewer')")
            conn.exec_driver_sql("INSERT INTO saas_runs VALUES ('run')")
        command.stamp(cfg,'122_company_cost_norms')
        command.upgrade(cfg,'126_private_review_order_links')
        command.downgrade(cfg,'125_private_review_retention')
        command.upgrade(cfg,'126_private_review_order_links')
        with engine.begin() as conn:
            for identity, tenant, raw, expires in (
                    ('a1','a',b'123',NOW), ('a2','a',b'4567',NOW+timedelta(days=1)),
                    ('b1','b',b'private-other',NOW)):
                conn.execute(text("""INSERT INTO application_review_previews
                    (id,tenant_id,member_id,run_id,procurement_ref,input_json,archive_bytes,
                    archive_sha256,plan_sha256,inputs_sha256,evidence_sha256,created_at,expires_at)
                    VALUES (:id,:tenant,'creator','run','fixture','{}',:raw,:sha,:sha,:sha,:sha,:created,:expires)"""),
                    {'id':identity,'tenant':tenant,'raw':raw,'sha':'a'*64,'created':NOW,'expires':expires})
            conn.execute(text("""INSERT INTO original_form_review_candidates
                (id,tenant_id,run_id,creator_id,reviewer_id,input_json,receipt_json,document_bytes,
                 document_sha256,candidate_sha256,created_at,expires_at)
                VALUES ('f1','a','run','creator','reviewer','{}','{}',:raw,:sha,:sha,:now,:now)"""),
                {'raw':b'12345','sha':'a'*64,'now':NOW})
        proposal=ScheduleProposal(order_ref='fixture-order',policy_ref='fixture-policy',
            working_days=30,backup_days=90,order_ended_on=date(2026,10,1),
            end_evidence_ref='fixture-evidence',hold_state='ACTIVE',
            hold_evidence_ref='fixture-hold',hold_review_on=NOW.date())
        with Session(engine) as session:
            session.add_all([PrivateReviewRetentionProposal(id='pa',tenant_id='a',revision=1,**proposal.model_dump()),
                             PrivateReviewRetentionProposal(id='pb',tenant_id='b',revision=1,**proposal.model_dump())])
            session.commit()
            for wrong in (
                {'tenant_id':'a','proposal_id':'pb','preview_id':'a1'},
                {'tenant_id':'a','proposal_id':'pa','preview_id':'b1'},
                {'tenant_id':'a','proposal_id':'pa','preview_id':'a1','candidate_id':'f1'},
                {'tenant_id':'a','proposal_id':'pa'},
            ):
                session.add(PrivateReviewOrderLink(evidence_ref='fixture-link',**wrong))
                with pytest.raises(IntegrityError):
                    session.commit()
                session.rollback()
            session.add_all([PrivateReviewOrderLink(tenant_id='a',proposal_id='pa',preview_id='a1',evidence_ref='link-a'),
                             PrivateReviewOrderLink(tenant_id='a',proposal_id='pa',candidate_id='f1',evidence_ref='link-f')])
            session.commit()
            result=storage_summary(session,tenant_id='a',now=NOW)
            a,f=result['archives'],result['forms']
            assert (a['count'],a['payload_bytes'],a['expired'],a['unlinked'],a['proposed_links'])==(2,7,1,1,1)
            assert (f['count'],f['payload_bytes'],f['expired'],f['proposed_links'])==(1,5,1,1)
            for row in (a,f):
                assert row['hold_active']==row['hold_review_due']==row['working_horizon_reached']==1
                assert row['backup_horizon_reached']==0
            assert result['deletion_authorized'] is result['order_ownership_verified'] is False
            assert 'fixture-' not in str(result)
            assert storage_summary(session,tenant_id='b',now=NOW)['archives']['payload_bytes']==13
            with pytest.raises(ValueError,match='Timezone-aware'):
                storage_summary(session,tenant_id='a',now=NOW.replace(tzinfo=None))
            session.add(PrivateReviewRetentionProposal(id='pa2',tenant_id='a',revision=2,**proposal.model_dump()))
            with pytest.raises(ValueError,match='Clean'):
                storage_summary(session,tenant_id='a',now=NOW)
            session.commit()
            stale=storage_summary(session,tenant_id='a',now=NOW)
            assert stale['archives']['proposal_superseded']==stale['forms']['proposal_superseded']==1
            assert stale['archives']['working_horizon_reached']==0
        with pytest.raises(RuntimeError,match='Cannot discard proposed'):
            command.downgrade(cfg,'125_private_review_retention')
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM private_review_order_links'))==2
    finally:
        engine.dispose()
        invalidate_settings_cache()
