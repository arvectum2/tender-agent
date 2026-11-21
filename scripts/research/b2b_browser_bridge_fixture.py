"""Actual Chrome + HTTPX + loopback origin acceptance, zero platform requests."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import httpx

from scripts.research.b2b_browser_bridge import (
    OfflineBrowserBridge,
    deny_proxy,
    launch_options,
)
from scripts.research.b2b_network_guard import WINDOW, EgressGate
from scripts.research.b2b_readonly_broker import ReadOnlyBroker

HTML=b'''<html><head><link rel="stylesheet" href="/fixture.css"></head><body><h1>Fixture 4664540</h1><button id="background" onclick="fetch('/background').then(r=>r.text()).then(t=>document.querySelector('#result').textContent=t)">Background</button><output id="result"></output><a id="download" href="/archive">Download ZIP</a><button id="limit" onclick="fetch('/limited').then(r=>document.querySelector('#result').textContent=r.status)">Limit</button></body></html>'''


def main():
    from playwright.sync_api import Error, sync_playwright

    output=BytesIO()
    with ZipFile(output,'w') as z:z.writestr('spec.txt','Offline fixture')
    archive=output.getvalue();seen=[]

    class Origin(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            seen.append(self.path)
            if self.path=='/entry':status,headers,body=302,{'Location':'/card'},b''
            elif self.path=='/card':status,headers,body=200,{'Content-Type':'text/html'},HTML
            elif self.path=='/fixture.css':status,headers,body=200,{'Content-Type':'text/css'},b'body {color: #123456}'
            elif self.path=='/background':status,headers,body=200,{'Content-Type':'text/plain'},b'background-ok'
            elif self.path=='/archive':status,headers,body=307,{'Location':'/file.zip'},b''
            elif self.path=='/file.zip':status,headers,body=200,{'Content-Type':'application/zip','Content-Disposition':'attachment; filename="fixture.zip"'},archive
            elif self.path=='/limited':status,headers,body=429,{'Retry-After':'90'},b''
            else:status,headers,body=500,{},b'unexpected direct traffic'
            self.send_response(status)
            for k,v in headers.items():self.send_header(k,v)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

    server=ThreadingHTTPServer(('127.0.0.1',0),Origin);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}';allowed={'/entry','/card','/fixture.css','/background','/archive','/file.zip','/limited','/favicon.ico'}
    # Favicon is explicitly blocked below, not passed to the origin.
    allowed.remove('/favicon.ico')
    try:
        with TemporaryDirectory() as tmp,deny_proxy() as (proxy,denied),sync_playwright() as driver:
            state=Path(tmp)/'state';state.mkdir(mode=0o700);clock=[10*WINDOW];gate=EgressGate(state,clock=lambda:clock[0],boot='offline-fixture');gate.initialize();clock[0]+=WINDOW
            broker=ReadOnlyBroker(gate,origin=origin,permitted=lambda url,method:httpx.URL(url).path in allowed and not httpx.URL(url).query,transport=httpx.HTTPTransport(retries=0,trust_env=False))
            # Browser without the accounting proxy cannot access the origin via
            # the rejecting proxy. No actual platform URLs are used.
            browser=driver.chromium.launch(**launch_options(proxy));context=browser.new_context(service_workers='block')
            try:
                page=context.new_page()
                try:page.goto(origin+'/direct-probe',timeout=3000)
                except Error:pass
                assert '/direct-probe' not in seen and denied
            finally:context.close();browser.close()
            bridge=OfflineBrowserBridge(broker)
            with bridge.serve() as accounting_proxy:
                browser=driver.chromium.launch(**launch_options(accounting_proxy));context=browser.new_context(accept_downloads=True,service_workers='block')
                try:
                    context.route_web_socket('**/*',lambda ws:ws.close(code=1008,reason='Offline read-only fixture'))
                    page=context.new_page()
                    page.goto(origin+'/entry',wait_until='load',timeout=7000)
                    assert page.url==origin+'/card',page.url
                    assert page.locator('h1').inner_text()=='Fixture 4664540'
                    page.locator('#background').click();page.wait_for_function("document.querySelector('#result').textContent === 'background-ok'",timeout=5000)
                    with page.expect_download(timeout=7000) as event:page.locator('#download').click()
                    dest=Path(tmp)/'fixture.zip';event.value.save_as(dest);assert dest.read_bytes()==archive
                    assert page.evaluate("fetch('/not-allowed').then(r=>r.status)")==403
                    assert page.evaluate("fetch('/background',{method:'POST'}).then(r=>r.status)")==403
                    page.locator('#limit').click();page.wait_for_function("document.querySelector('#result').textContent === '429'",timeout=5000)
                    assert page.evaluate("fetch('/background').then(r=>r.status)")==403
                    assert seen==['/entry','/card','/fixture.css','/background','/archive','/file.zip','/limited'],seen
                    receipts=json.loads(gate.state.read_text())['receipts'];assert len(receipts)==len(seen) and receipts[-1]['status']==429
                    assert bridge.stopped and bridge.events[-1]=='BLOCKED'
                    print('CHROME LOOPBACK BRIDGE PASS',json.dumps({'origin_requests':len(seen),'charged':len(receipts),'download_bytes':len(archive),'direct_proxy_denied':len(denied),'status':[r['status'] for r in receipts]}))
                finally:context.close();browser.close();broker.close()

    finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
