"""Concurrent authenticated ASGI requests against a disposable PostgreSQL fixture.

Opt in only through run_apr04_form_review_postgres.py. The source observation
is synthetic; actual authorization, candidate checks, transactions and audit
writes execute in the application.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from test_apr05_saas_foundation import enabled  # noqa: F401
from test_authenticated_application_review import review  # noqa: F401
from test_independent_original_form_review import ack, create, scenario  # noqa: F401

from src.main import app
from src.modules.saas_foundation.models import OriginalFormReviewReceipt, SaasAuditEvent
from src.shared.api.dependencies import get_db_session
from src.shared.db.base import Base

pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_APR04_FORM_REVIEW_PG') != '1',
    reason='requires disposable APR04 PostgreSQL acceptance runner',
)


@pytest.fixture
def pg_factory():
    url = make_url(os.environ['AI_CORP_DATABASE_URL'])
    socket = Path(url.query.get('host', ''))
    if (url.drivername != 'postgresql+psycopg' or url.username != 'apr04_fixture_owner'
            or url.host is not None or url.database != 'api_fixture'
            or socket.parent.parent != Path('/tmp').resolve() or not socket.parent.name.startswith('ta-apr04-review-pg-')
            or socket.name != 'socket' or not socket.is_dir()):
        raise RuntimeError('Refusing non-disposable PostgreSQL target')
    engine = create_engine(url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def session(pg_factory):
    with pg_factory() as db:
        yield db


@pytest.fixture
def client(pg_factory):
    def request_session():
        with pg_factory() as db:
            yield db
    app.dependency_overrides[get_db_session] = request_session
    try:
        with TestClient(app) as http:
            yield http
    finally:
        app.dependency_overrides.pop(get_db_session, None)


def test_concurrent_independent_review_receipt(client, pg_factory, scenario):  # noqa: F811
    p = create(client, scenario)
    barrier = Barrier(2)

    def request(_):
        barrier.wait(timeout=10)
        response = ack(client, scenario, p)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['status'] == 'INDEPENDENT_INTERNAL_REVIEW_RECORDED'
        assert data['application_ready'] is False
        assert data['external_export_allowed'] is False
        return data['receipt_id']

    with ThreadPoolExecutor(max_workers=2) as workers:
        receipts = list(workers.map(request, range(2)))
    assert receipts[0] == receipts[1]
    with pg_factory() as db:
        assert db.scalar(select(func.count(OriginalFormReviewReceipt.id))) == 1
        row = db.get(OriginalFormReviewReceipt, receipts[0])
        assert row.candidate_id == p['candidate_id']
        assert row.document_sha256 == p['document_sha256']
        assert db.scalar(select(func.count(SaasAuditEvent.id)).where(
            SaasAuditEvent.event_type == 'original_form_review_recorded',
            SaasAuditEvent.detail == receipts[0])) == 1
