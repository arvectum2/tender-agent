"""Actual Chrome HTTPS acceptance using two ephemeral loopback TLS identities."""
from __future__ import annotations

import base64
import hashlib
import json
import ssl
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import httpx

from scripts.research.b2b_browser_bridge import launch_options
from scripts.research.b2b_https_fixture_bridge import OfflineTLSBridge
from scripts.research.b2b_network_guard import WINDOW, EgressGate, GuardError
from scripts.research.b2b_readonly_broker import ReadOnlyBroker

HTML=b'''<html><head><link rel="stylesheet" href="/style.css"></head><body><h1>Authorized fixture</h1><button id="background" onclick="fetch('/background').then(r=>r.text()).then(t=>document.querySelector('#result').textContent=t)">Background</button><output id="result"></output><a id="download" href="/archive">Download ZIP</a><button id="limit" onclick="fetch('/limited').then(r=>document.querySelector('#result').textContent=r.status)">Limit</button></body></html>'''
PATHS={'/session','/card','/style.css','/background','/archive','/file.zip','/limited'}
SYNTHETIC_COOKIE='fixture_session=local-only-synthetic'


def identity(directory,name):
    key=directory/(name+'.key');cert=directory/(name+'.pem')
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    key.chmod(0o600)
    pub=subprocess.check_output(['openssl','x509','-in',str(cert),'-pubkey','-noout'],timeout=5)
    der=subprocess.check_output(['openssl','pkey','-pubin','-outform','DER'],input=pub,timeout=5)
    pin=base64.b64encode(hashlib.sha256(der).digest()).decode()
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2;ctx.load_cert_chain(cert,key);ctx.set_alpn_protocols(['http/1.1'])
    return cert,ctx,pin


@contextmanager
def origin_server(context):
    output=BytesIO()
    with ZipFile(output,'w') as z:z.writestr('spec.txt','Offline TLS fixture')
    archive=output.getvalue();seen=[]
    class Origin(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            seen.append(self.path)
            if self.path=='/session':status,headers,body=302,{'Location':'/card','Set-Cookie':SYNTHETIC_COOKIE+'; Path=/; Secure; HttpOnly; SameSite=Strict'},b''
            elif self.headers.get('Cookie')!=SYNTHETIC_COOKIE:status,headers,body=401,{},b'no fixture session'
            elif self.path=='/card':status,headers,body=200,{'Content-Type':'text/html'},HTML
            elif self.path=='/style.css':status,headers,body=200,{'Content-Type':'text/css'},b'body {color: #123456}'
            elif self.path=='/background':status,headers,body=200,{'Content-Type':'text/plain'},b'background-ok'
            elif self.path=='/archive':status,headers,body=307,{'Location':'/file.zip'},b''
            elif self.path=='/file.zip':status,headers,body=200,{'Content-Type':'application/zip','Content-Disposition':'attachment; filename="fixture.zip"'},archive
            elif self.path=='/limited':status,headers,body=429,{'Retry-After':'90'},b''
            else:status,headers,body=500,{},b'unexpected request'
            self.send_response(status)
            for k,v in headers.items():self.send_header(k,v)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Origin);server.socket=context.wrap_socket(server.socket,server_side=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'https://127.0.0.1:{server.server_port}',seen,archive
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


def main():
    from playwright.sync_api import Error, sync_playwright

    with TemporaryDirectory() as tmp,sync_playwright() as driver:
        root=Path(tmp);upstream,origin_ctx,_=identity(root,'origin');_,proxy_ctx,pin=identity(root,'proxy')
        trust=ssl.create_default_context(cafile=str(upstream));trust.minimum_version=ssl.TLSVersion.TLSv1_2
        with origin_server(origin_ctx) as (origin,seen,archive):
            state=root/'state';state.mkdir(mode=0o700);clock=[10*WINDOW];gate=EgressGate(state,clock=lambda:clock[0],boot='offline-tls');gate.initialize();clock[0]+=WINDOW
            def permitted(url,method):return httpx.URL(url).path in PATHS and not httpx.URL(url).query
            bad=ReadOnlyBroker(gate,origin=origin,permitted=permitted,transport=httpx.HTTPTransport(retries=0,trust_env=False))
            try:
                try:bad.fetch_one(origin+'/session');raise AssertionError('Untrusted fixture TLS unexpectedly accepted')
                except GuardError:pass
                assert seen==[] and json.loads(gate.state.read_text())['receipts'][-1]['status'] is None
            finally:bad.close()
            broker=ReadOnlyBroker(gate,origin=origin,permitted=permitted,transport=httpx.HTTPTransport(verify=trust,retries=0,trust_env=False))
            bridge=OfflineTLSBridge(broker,context=proxy_ctx)
            with bridge.serve() as proxy:
                browser=driver.chromium.launch(**launch_options(proxy));context=browser.new_context(service_workers='block',ignore_https_errors=False)
                try:
                    page=context.new_page()
                    try:page.goto(origin+'/session',timeout=3000);raise AssertionError('Untrusted browser TLS unexpectedly accepted')
                    except Error as err:assert 'CERT' in str(err) or 'SSL' in str(err),str(err)
                    assert seen==[]
                finally:context.close();browser.close()
                options=launch_options(proxy);options['args'].append('--ignore-certificate-errors-spki-list='+pin)
                browser=driver.chromium.launch(**options);context=browser.new_context(accept_downloads=True,service_workers='block',ignore_https_errors=False)
                try:
                    context.route_web_socket('**/*',lambda ws:ws.close(code=1008,reason='Offline read-only fixture'))
                    page=context.new_page();page.goto(origin+'/session',wait_until='load',timeout=7000)
                    assert page.url==origin+'/card' and page.locator('h1').inner_text()=='Authorized fixture'
                    page.locator('#background').click();page.wait_for_function("document.querySelector('#result').textContent === 'background-ok'",timeout=5000)
                    with page.expect_download(timeout=7000) as event:page.locator('#download').click()
                    dest=root/'fixture.zip';event.value.save_as(dest);assert dest.read_bytes()==archive
                    assert page.evaluate("fetch('/background',{method:'POST'}).then(r=>r.status)")==403
                    assert page.evaluate("fetch('/not-allowed').then(r=>r.status)")==403
                    page.locator('#limit').click();page.wait_for_function("document.querySelector('#result').textContent === '429'",timeout=5000)
                    assert page.evaluate("fetch('/background').then(r=>r.status)")==403
                    assert seen==['/session','/card','/style.css','/background','/archive','/file.zip','/limited'],seen
                    receipts=json.loads(gate.state.read_text())['receipts'];assert len(receipts)==len(seen)+1 and [r['status'] for r in receipts]==[None,302,200,200,200,307,200,429]
                    assert SYNTHETIC_COOKIE not in gate.state.read_text() and bridge.stopped
                    print('CHROME HTTPS LOOPBACK PASS',json.dumps({'origin_requests':len(seen),'charged':len(receipts),'failed_tls_charged':1,'download_bytes':len(archive),'browser_untrusted_tls_refused':True,'broker_cookie_session':True}))
                finally:context.close();browser.close();broker.close()
            clock[0]+=90_000_000_000
            other=ReadOnlyBroker(gate,origin=origin,permitted=permitted,transport=httpx.HTTPTransport(verify=trust,retries=0,trust_env=False))
            try:assert other.fetch_one(origin+'/card').status==401
            finally:other.close()


if __name__=='__main__':main()
