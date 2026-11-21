"""Opt-in real Chromium / loopback FastAPI acceptance with synthetic data."""
import json
import os
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import func, select
from test_apr05_saas_foundation import _operator, enabled  # noqa: F401
from test_authenticated_application_review import create, review  # noqa: F401
from test_original_form_review_live_browser import (  # noqa: F401
    client,
    isolated_factory,
    loopback,
    session,
)

from src.modules.saas_foundation import router
from src.modules.saas_foundation.models import (
    ApplicationReviewPreview,
    PrivateReviewOrderLink,
    PrivateReviewRetentionProposal,
)

pytestmark = pytest.mark.skipif(os.environ.get('RUN_APR04_LIVE_BROWSER') != '1', reason='explicit local browser acceptance')
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('width',[1280,390])
def test_retention_operator_actual_browser(client, session, review, loopback, monkeypatch, width):  # noqa: F811
    p=create(client,review)
    tenant=session.get(ApplicationReviewPreview,p['preview_id']).tenant_id
    settings=review[-1].model_copy(update={'saas_retention_operator_enabled':True})
    monkeypatch.setattr(router,'get_settings',lambda:settings)
    config={'origin':loopback,'tenant':tenant,'document':p['preview_id'],'auth':_operator(client)['Authorization'],'width':width}
    result=subprocess.run([os.environ['APR04_NODE'],str(ROOT/'scripts/acceptance/run_retention_operator_browser.cjs')],
        cwd=ROOT,input=json.dumps(config),text=True,capture_output=True,timeout=35,check=False)
    assert result.returncode==0,result.stderr[:1500]
    assert 'RETENTION_OPERATOR_BROWSER_PASS '+str(width) in result.stdout
    assert session.scalar(select(func.count(PrivateReviewOrderLink.id)))==1
    assert session.scalar(select(func.count(PrivateReviewRetentionProposal.id)))==2
