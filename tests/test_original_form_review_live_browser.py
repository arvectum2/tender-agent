"""Opt-in real Chromium against a local FastAPI server; synthetic fixture only."""
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_apr05_saas_foundation import enabled  # noqa: F401
from test_authenticated_application_review import review  # noqa: F401
from test_independent_original_form_review import scenario  # noqa: F401

from src.main import app
from src.modules.saas_foundation.models import OriginalFormReviewReceipt, SaasAuditEvent
from src.shared.api.dependencies import get_db_session
from src.shared.db.base import Base

pytestmark = pytest.mark.skipif(os.environ.get('RUN_APR04_LIVE_BROWSER') != '1',
                               reason='requires explicit local Chromium acceptance')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_factory(tmp_path):
    engine = create_engine('sqlite:///'+str(tmp_path/'browser-fixture.sqlite'),
                           connect_args={'check_same_thread':False})
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def session(isolated_factory):
    with isolated_factory() as db:
        yield db


@pytest.fixture
def client(isolated_factory):
    def request_session():
        with isolated_factory() as db:
            yield db
    app.dependency_overrides[get_db_session] = request_session
    try:
        with TestClient(app) as http:
            yield http
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def loopback():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1',0))
        listener.listen(32)
        origin='http://127.0.0.1:'+str(listener.getsockname()[1])
        server=uvicorn.Server(uvicorn.Config(app,log_level='warning',access_log=False,lifespan='off'))
        thread=Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
        thread.start()
        try:
            deadline=time.monotonic()+10
            while not server.started and thread.is_alive() and time.monotonic()<deadline:
                time.sleep(0.01)
            assert server.started
            yield origin
        finally:
            server.should_exit=True
            thread.join(timeout=10)
            assert not thread.is_alive()


@pytest.mark.parametrize('width',[1280,390])
def test_browser_live_independent_form_review(scenario, loopback, isolated_factory, width):  # noqa: F811
    config={'origin':loopback,'run_id':'toa-run-fixture-approval','width':width,
            'creator':scenario['creator'],'reviewer':scenario['reviewer'],
            'reviewer_id':scenario['payload']['reviewer_id'],
            'map':{k:v for k,v in scenario['payload'].items() if k!='reviewer_id'}}
    result=subprocess.run([os.environ['APR04_NODE'],str(ROOT/'scripts/acceptance/run_original_form_review_live_browser.cjs')],
                          cwd=ROOT,input=json.dumps(config),text=True,capture_output=True,timeout=45,check=False)
    assert result.returncode==0, 'Browser fixture failed: '+result.stderr[:1500]
    assert 'LIVE_LOOPBACK_BROWSER_PASS '+str(width) in result.stdout
    with isolated_factory() as db:
        assert db.scalar(select(func.count(OriginalFormReviewReceipt.id)))==1
        assert db.scalar(select(func.count(SaasAuditEvent.id)).where(
            SaasAuditEvent.event_type=='original_form_review_recorded'))==1
