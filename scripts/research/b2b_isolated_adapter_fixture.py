"""Verify port-specific macOS network confinement and HTTPS broker with real Chrome."""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from scripts.research.b2b_https_fixture import (
    PATHS,
    SYNTHETIC_COOKIE,
    identity,
    origin_server,
)
from scripts.research.b2b_isolated_broker import RendererBroker
from scripts.research.b2b_network_guard import WINDOW, EgressGate
from scripts.research.b2b_readonly_broker import ReadOnlyBroker
from scripts.research.b2b_session_policy import ExactScope


def main():
    if sys.platform!='darwin':raise RuntimeError('macOS fixture requires sandbox-exec')
    with TemporaryDirectory() as tmp:
        root=Path(tmp);cert,ctx,_=identity(root,'origin');trust=ssl.create_default_context(cafile=str(cert));trust.minimum_version=ssl.TLSVersion.TLSv1_2
        with origin_server(ctx) as (origin,seen,archive):
            state=root/'state';state.mkdir(mode=0o700);clock=[10*WINDOW];gate=EgressGate(state,clock=lambda:clock[0],boot='isolated-fixture');gate.initialize();clock[0]+=WINDOW
            scope=ExactScope(origin,{origin+p:'archive' if p in ('/archive','/file.zip') else 'page' if p in ('/session','/card') else 'asset' for p in PATHS})
            broker=ReadOnlyBroker(gate,origin=origin,permitted=scope,transport=httpx.HTTPTransport(verify=trust,retries=0,trust_env=False))
            try:
                # Explicit reviewed initial navigation via verified upstream TLS.
                initial=broker.fetch_one(origin+'/session');assert initial.status==302 and broker.redirect_target(initial,'GET')==origin+'/card'
                adapter=RendererBroker(broker,scope)
                with adapter.serve() as port:
                    profile=f'(version 1)(allow default)(deny network*)(allow network-bind (local unix-socket))(allow network-outbound (remote tcp "localhost:{port}"))'
                    cfg={'port':port,'token':adapter.token,'origin':origin,'card':origin+'/card','directory':str(root),'mode':'offline-fixture'}
                    result=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,sys.executable,'-m','scripts.research.b2b_renderer_worker'],input=json.dumps(cfg),text=True,capture_output=True,timeout=45,env=os.environ.copy(),check=False)
                    assert result.returncode==0,result.stdout[-1000:]+' '+result.stderr[-1500:]
                    receipt=json.loads(result.stdout);assert receipt['sandbox_negative_probe'] and receipt['page_identity']
                assert seen==['/session','/card','/style.css','/background','/archive','/file.zip','/limited'],seen
                assert (root/'fixture.zip').read_bytes()==archive
                logged=json.loads(gate.state.read_text())['receipts'];assert len(logged)==len(seen) and logged[-1]['status']==429
                assert SYNTHETIC_COOKIE not in gate.state.read_text() and adapter.stopped
                print('ISOLATED CHROME HTTPS PASS',json.dumps({'origin_requests':len(seen),'charged':len(logged),'TLS_interception':False,'certificate_exception':False,'sandbox_negative_probe':True,'download_bytes':len(archive)}))
            finally:broker.close()


if __name__=='__main__':main()
