"""Private loopback IPC for a sandboxed renderer. No real-site TLS interception.

The local HTTPS client is the sole upstream caller. The renderer receives bounded
responses only; redirects cannot silently change page identity. This module is
not a live activation command.
"""
from __future__ import annotations

import base64
import hmac
import json
import secrets
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.research.b2b_network_guard import GuardError, WaitRequired
from scripts.research.b2b_readonly_broker import MAX_REDIRECTS, REDIRECTS


class RendererBroker:
    def __init__(self,broker,scope,*,seconds=65):
        if not 1<=seconds<=120:raise GuardError('Invalid pilot deadline')
        self.broker=broker;self.scope=scope;self.deadline=time.monotonic()+seconds
        self.token=secrets.token_hex(32);self.lock=threading.Lock();self.stopped=False;self.events=[]

    def fetch(self,url,method):
        with self.lock:
            if self.stopped or time.monotonic()>=self.deadline:raise GuardError('Pilot stopped or expired')
            if not self.scope(url,method):raise GuardError('Unreviewed renderer route')
            try:
                kind=self.scope.kind(url)
                if kind=='archive':
                    if method!='GET':raise GuardError('Archive download requires GET')
                    target=url
                    for hop in range(MAX_REDIRECTS+1):
                        if self.scope.kind(target)!='archive' or time.monotonic()>=self.deadline:raise GuardError('Unexpected archive target or expired deadline')
                        r=self.broker.fetch_one(target,method)
                        if r.status not in REDIRECTS:break
                        if hop==MAX_REDIRECTS:raise GuardError('Archive redirect limit exceeded')
                        target=self.broker.redirect_target(r,method)
                else:r=self.broker.fetch_one(url,method)
                if r.status in REDIRECTS:raise GuardError('Navigation redirect requires explicit reviewed navigation')
                if r.status in (401,403,429):self.stopped=True
                if time.monotonic()>=self.deadline:raise GuardError('Pilot deadline exceeded')
                headers={k:v for k,v in r.headers if k.lower() in ('content-type','content-disposition','retry-after','cache-control')}
                if kind=='archive' and r.status==200 and (not r.data.startswith(b'PK') or 'attachment' not in headers.get('content-disposition','').lower()):raise GuardError('Invalid archive response')
                self.events.append(r.status);return r.status,headers,r.data
            except (GuardError,OSError):self.stopped=True;raise

    @contextmanager
    def serve(self):
        adapter=self
        class Handler(BaseHTTPRequestHandler):
            def setup(self):super().setup();self.connection.settimeout(8)
            def log_message(self,*args):pass
            def reply(self,status,body=b'',meta=None):
                self.send_response(status);self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close')
                if meta:self.send_header('X-Renderer-Receipt',base64.b64encode(json.dumps(meta,separators=(',',':')).encode()).decode())
                self.end_headers();self.close_connection=True
                if body:self.wfile.write(body)
            def deny(self):self.reply(403)
            do_GET=do_HEAD=do_CONNECT=do_DELETE=do_PUT=do_OPTIONS=do_PATCH=deny
            def do_POST(self):
                if self.path!='/fetch' or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+adapter.token):return self.deny()
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 1<=length<=4096 or self.headers.get('Transfer-Encoding'):raise ValueError
                    payload=json.loads(self.rfile.read(length))
                    if not isinstance(payload,dict) or set(payload)!={'url','method'} or not all(isinstance(v,str) for v in payload.values()):raise ValueError
                    status,headers,data=adapter.fetch(payload['url'],payload['method'])
                    self.reply(200,data,{'status':status,'headers':headers})
                except WaitRequired:self.reply(429)
                except (ValueError,GuardError,OSError):self.deny()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield server.server_port
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
