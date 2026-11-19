"""Disposable Unix-socket PostgreSQL 16 migration/constraint/restore acceptance.

Only synthetic schema prerequisites and rows; no deployment credentials,
real documents, or service database. Also exercises concurrent ASGI requests.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Barrier

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from src.modules.saas_foundation.models import (
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
)
from src.modules.saas_foundation.private_review_retention import (
    ScheduleProposal,
    describe,
    latest_proposal,
    storage_summary,
)
from src.shared.config.settings import invalidate_settings_cache

ROOT = Path(__file__).resolve().parents[2]


def main():
    bindir = Path(subprocess.check_output(['pg_config', '--bindir'], text=True).strip())
    if 'PostgreSQL) 16.' not in subprocess.check_output([str(bindir/'postgres'), '--version'], text=True):
        raise RuntimeError('PostgreSQL 16 binaries required')
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
    env.update(LC_ALL='C', LANG='C')
    with tempfile.TemporaryDirectory(prefix='ta-apr04-review-pg-', dir='/tmp') as folder:
        root = Path(folder).resolve()
        data, sock = root/'pg', root/'socket'
        sock.mkdir(mode=0o700)
        role = 'apr04_fixture_owner'
        port = '55439'

        def run(binary, *args):
            subprocess.run([str(bindir/binary), *args], env=env, check=True, timeout=30, capture_output=True)

        def url(db):
            return f'postgresql+psycopg://{role}@/{db}?host={sock}&port={port}'

        def db_args(db):
            return ('-h', str(sock), '-p', port, '-U', role, '-d', db)

        previous = os.environ.get('AI_CORP_DATABASE_URL')
        started = False
        engine = restored = None
        try:
            run('initdb', '-D', str(data), '-U', role, '-A', 'trust', '--no-locale', '-E', 'UTF8')
            run('pg_ctl', '-D', str(data), '-l', str(root/'pg.log'), '-o', f"-h '' -k {sock} -p {port}", '-w', 'start')
            started = True
            os.environ['AI_CORP_DATABASE_URL'] = url('postgres')
            invalidate_settings_cache()
            engine = create_engine(url('postgres'))
            cfg = Config(str(ROOT/'alembic.ini'))
            with engine.begin() as conn:
                for table, column in (('saas_tenants','tenant_id'), ('saas_members','id'), ('saas_runs','run_id')):
                    conn.exec_driver_sql(f'CREATE TABLE {table} ({column} VARCHAR PRIMARY KEY)')
                conn.exec_driver_sql("INSERT INTO saas_tenants VALUES ('tenant')")
                conn.exec_driver_sql("INSERT INTO saas_members VALUES ('creator'),('reviewer')")
                conn.exec_driver_sql("INSERT INTO saas_runs VALUES ('run')")
            command.stamp(cfg, '122_company_cost_norms')
            command.upgrade(cfg, '123_application_review')
            command.upgrade(cfg, '124_original_form_review')
            command.downgrade(cfg, '123_application_review')
            command.upgrade(cfg, '124_original_form_review')
            print('PG16_MIGRATION_124_EMPTY_ROUNDTRIP_PASS')
            raw = b'synthetic-test-document'
            sha = hashlib.sha256(raw).hexdigest()
            candidate_sql = text("""INSERT INTO original_form_review_candidates
                (id,tenant_id,run_id,creator_id,reviewer_id,input_json,receipt_json,document_bytes,
                 document_sha256,candidate_sha256,created_at,expires_at)
                VALUES (:id,'tenant','run','creator',:reviewer,'{}','{}',:raw,:sha,:sha,now(),now()+interval '30 minutes')""")
            with engine.begin() as conn:
                conn.execute(candidate_sql, {'id':'candidate','reviewer':'reviewer','raw':raw,'sha':sha})
            try:
                with engine.begin() as conn:
                    conn.execute(candidate_sql, {'id':'invalid','reviewer':'creator','raw':raw,'sha':sha})
            except IntegrityError as exc:
                assert exc.orig.sqlstate == '23514'
            else:
                raise AssertionError('Self-review candidate accepted')
            barrier = Barrier(2)

            def insert_receipt(index):
                try:
                    with engine.begin() as conn:
                        barrier.wait(timeout=10)
                        conn.execute(text("""INSERT INTO original_form_review_receipts
                            VALUES (:id,'candidate','reviewer',:sha,:sha,now())"""),
                                     {'id':f'receipt-{index}','sha':sha})
                    return 'inserted'
                except IntegrityError as exc:
                    assert exc.orig.sqlstate == '23505'
                    return 'duplicate'

            with ThreadPoolExecutor(max_workers=2) as pool:
                assert sorted(pool.map(insert_receipt, range(2))) == ['duplicate','inserted']
            print('PG16_DISTINCT_CREATOR_AND_UNIQUE_CONCURRENT_RECEIPT_PASS')
            try:
                command.downgrade(cfg, '123_application_review')
            except RuntimeError as exc:
                assert 'Cannot discard original form review history' in str(exc)
            else:
                raise AssertionError('Nonempty downgrade allowed')
            with engine.connect() as conn:
                expected = conn.execute(text('SELECT * FROM original_form_review_candidates')).all()
                receipt = conn.execute(text('SELECT * FROM original_form_review_receipts')).all()
                assert len(expected) == len(receipt) == 1
                assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '124_original_form_review'
            print('PG16_NONEMPTY_DOWNGRADE_REFUSED_PASS')
            dump = root/'fixture.dump'
            run('pg_dump', *db_args('postgres'), '-Fc', '-f', str(dump))
            run('createdb', '-h', str(sock), '-p', port, '-U', role, 'restored')
            run('pg_restore', *db_args('restored'), '--exit-on-error', str(dump))
            restored = create_engine(url('restored'))
            with restored.connect() as conn:
                assert conn.execute(text('SELECT * FROM original_form_review_candidates')).all() == expected
                assert conn.execute(text('SELECT * FROM original_form_review_receipts')).all() == receipt
                assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '124_original_form_review'
            print('PG16_SYNTHETIC_BACKUP_RESTORE_EXACT_ROWS_PASS')
            command.upgrade(cfg, '125_private_review_retention')
            command.downgrade(cfg, '124_original_form_review')
            command.upgrade(cfg, '125_private_review_retention')
            proposal = ScheduleProposal(order_ref='fixture-order', policy_ref='fixture-policy',
                working_days=30, backup_days=90, order_ended_on=date(2026,10,1), end_evidence_ref='fixture-end')
            with Session(engine) as session:
                session.add(PrivateReviewRetentionProposal(tenant_id='tenant',revision=1,**proposal.model_dump()))
                session.commit()
                row=latest_proposal(session,tenant_id='tenant',order_ref='fixture-order')
                assert row.revision==1 and row.hold_state=='UNKNOWN'
                assert latest_proposal(session,tenant_id='other',order_ref='fixture-order') is None
                assert describe(proposal,as_of=date(2026,11,19))['deletion_authorized'] is False
            try:
                command.downgrade(cfg,'124_original_form_review')
            except RuntimeError as exc:
                assert 'Cannot discard retention proposal history' in str(exc)
            else:
                raise AssertionError('Nonempty proposal downgrade allowed')
            with engine.connect() as conn:
                assert conn.scalar(text('SELECT count(*) FROM private_review_retention_proposals')) == 1
                assert conn.scalar(text('SELECT count(*) FROM original_form_review_candidates')) == 1
            print('PG16_RETENTION_PROPOSAL_ROUNDTRIP_AND_GUARD_PASS')
            command.upgrade(cfg, '126_private_review_order_links')
            command.downgrade(cfg, '125_private_review_retention')
            command.upgrade(cfg, '126_private_review_order_links')
            with engine.begin() as conn:
                conn.exec_driver_sql("INSERT INTO saas_tenants VALUES ('other')")
            with Session(engine) as session:
                pinned=latest_proposal(session,tenant_id='tenant',order_ref='fixture-order')
                for wrong in (
                    {'tenant_id':'other','proposal_id':pinned.id,'candidate_id':'candidate'},
                    {'tenant_id':'tenant','proposal_id':pinned.id,'candidate_id':'missing'},
                ):
                    session.add(PrivateReviewOrderLink(evidence_ref='fixture',**wrong))
                    try:
                        session.commit()
                    except IntegrityError as exc:
                        assert exc.orig.sqlstate=='23503'
                        session.rollback()
                    else:
                        raise AssertionError('Wrong tenant or missing document accepted')
                session.add(PrivateReviewOrderLink(tenant_id='tenant',proposal_id=pinned.id,
                                                   candidate_id='candidate',evidence_ref='fixture'))
                session.commit()
                observed=storage_summary(session,tenant_id='tenant',now=datetime.now(UTC))
                assert observed['forms']['payload_bytes']==len(raw)
                assert observed['forms']['proposed_links']==1
                assert observed['forms']['hold_unknown']==1
                assert observed['deletion_authorized'] is False
                assert storage_summary(session,tenant_id='other',now=datetime.now(UTC))['forms']['count']==0
            try:
                command.downgrade(cfg,'125_private_review_retention')
            except RuntimeError as exc:
                assert 'Cannot discard proposed document-order links' in str(exc)
            else:
                raise AssertionError('Nonempty order link history discarded')
            with engine.connect() as conn:
                assert conn.scalar(text('SELECT count(*) FROM private_review_order_links'))==1
            print('PG16_DOCUMENT_ORDER_LINKS_AND_ACCOUNTING_PASS')


            run('createdb', '-h', str(sock), '-p', port, '-U', role, 'api_fixture')
            api_env = dict(env, AI_CORP_DATABASE_URL=url('api_fixture'),
                           AI_CORP_ARVECTUM_DATA_DIR=str(root/'api-data'),
                           RUN_R8_POSTGRES_INTEGRATION='1', RUN_APR04_FORM_REVIEW_PG='1')
            subprocess.run([sys.executable, '-m', 'pytest', '-q',
                'tests/test_original_form_review_pg_concurrency.py', '--run-postgres'],
                cwd=ROOT, env=api_env, check=True, timeout=60)
            print('PG16_CONCURRENT_AUTHENTICATED_ASGI_REVIEW_PASS')

        finally:
            if engine:
                engine.dispose()
            if restored:
                restored.dispose()
            if previous is None:
                os.environ.pop('AI_CORP_DATABASE_URL', None)
            else:
                os.environ['AI_CORP_DATABASE_URL'] = previous
            invalidate_settings_cache()
            if started:
                run('pg_ctl', '-D', str(data), '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    main()
