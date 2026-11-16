"""Disposable Chromium renderer launched under a port-specific network sandbox.

No upstream client, credentials, persistent profile, certificate override or
user-supplied script. Private IPC requests ask the parent broker for bytes.
"""
from __future__ import annotations

import base64
import errno
import http.client
import json
import re
import socket
import sys
from pathlib import Path

from scripts.research.b2b_browser_bridge import launch_options
from scripts.research.commercial_document_acquisition import observe

MAX_RESPONSE=25*1024*1024


def assert_restricted(port):
    # Negative socket probe, no real external network request.
    with socket.socket() as s:
        s.settimeout(2)
        if s.connect_ex(('127.0.0.1',port+1 if port<65535 else port-1)) not in (errno.EPERM,errno.EACCES):raise RuntimeError('Renderer network restriction not established')


def render(cfg):
    from playwright.sync_api import sync_playwright

    port=cfg['port'];assert_restricted(port);token=cfg['token'];origin=cfg['origin'];card=cfg['card'];root=Path(cfg['directory']);events=[]
    def route_request(route):
        request=route.request
        if request.method not in ('GET','HEAD') or not request.url.startswith(origin+'/') or request.resource_type in ('websocket','eventsource','media'):
            events.append('blocked');route.abort();return
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=25)
        try:
            c.request('POST','/fetch',json.dumps({'url':request.url,'method':request.method}),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            r=c.getresponse()
            if r.status!=200:events.append('blocked');route.abort();return
            meta=json.loads(base64.b64decode(r.getheader('X-Renderer-Receipt'),validate=True));size=int(r.getheader('Content-Length'))
            if not 0<=size<=MAX_RESPONSE:raise ValueError
            data=r.read(MAX_RESPONSE+1)
            if len(data)!=size:raise ValueError
            events.append(meta['status']);route.fulfill(status=meta['status'],headers=meta['headers'],body=data)
        except Exception:  # noqa: BLE001 -- fail closed, never print untrusted URLs or details
            events.append('failed');route.abort()
        finally:c.close()
    with sync_playwright() as driver:
        browser=driver.chromium.launch(**launch_options(f'http://127.0.0.1:{port}'));context=browser.new_context(accept_downloads=True,service_workers='block',ignore_https_errors=False)
        try:
            context.route('**/*',route_request);context.route_web_socket('**/*',lambda ws:ws.close(code=1008,reason='Read-only renderer'))
            page=context.new_page();response=page.goto(card,wait_until='load',timeout=10000)
            if page.url!=card or response is None or response.status!=200:raise RuntimeError('Page identity or navigation failed')
            # Candidate one-card workflow: no downloads, navigation or submission.
            # A local operator must verify the account outside this renderer.
            if cfg['mode']=='case-review':
                result=observe(page,card,authenticated=False)
                body=page.locator('body').inner_text(timeout=3000)
                if len(body)>500000:raise RuntimeError('Bounded body exceeded')
                normalized=' '.join(body.casefold().replace('ё','е').split())
                return {'state':result['state'],'visible_controls':result['visible_controls'],'body_sha256':result['body_sha256'],'external_id':result['external_id'],'card_id_visible':bool(re.search(r'(?<!\d)'+result['external_id']+r'(?!\d)',body)),'login_text_seen':any(x in normalized for x in ('войти в систему','вход в личный кабинет','введите логин','введите пароль')),'account_identity_verified':False,'external_submission_allowed':False,'events':events,'sandbox_negative_probe':True}
            if cfg['mode']!='offline-fixture':raise RuntimeError('Unknown renderer workflow')
            assert page.locator('h1').inner_text()=='Authorized fixture'
            page.locator('#background').click();page.wait_for_function("document.querySelector('#result').textContent === 'background-ok'",timeout=5000)
            with page.expect_download(timeout=10000) as event:page.locator('#download').click()
            event.value.save_as(root/'fixture.zip')
            page.locator('#limit').click();page.wait_for_function("document.querySelector('#result').textContent === '429'",timeout=5000)
            page.evaluate("fetch('/background').catch(()=>null)")
            return {'events':events,'sandbox_negative_probe':True,'page_identity':True}
        finally:context.close();browser.close()


def main():
    cfg=json.loads(sys.stdin.read(16385))
    try:print(json.dumps(render(cfg)))
    except Exception as exc:  # noqa: BLE001 -- sanitized boundary
        print(json.dumps({'error_type':type(exc).__name__}));
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
