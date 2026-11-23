"""TLS-terminating LOCAL TEST proxy, never a live-site interception proxy.

Only a single literal loopback HTTPS authority is accepted. A disposable test
certificate terminates that CONNECT locally; it is never a byte tunnel. Every
inner HTTP request is independently admitted, and the HTTPX upstream validates
its separate fixture certificate. No trust-store installation or live credentials.
"""
from __future__ import annotations

import ssl
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from scripts.research.b2b_network_guard import GuardError, WaitRequired
from scripts.research.b2b_readonly_broker import REDIRECTS


class OfflineTLSBridge:
    def __init__(self,broker,*,context):
        scheme,authority=broker.origin
        host=urlsplit(f'https://{authority}')
        if scheme!='https' or host.hostname!='127.0.0.1' or host.port is None or authority!=f'127.0.0.1:{host.port}':
            raise GuardError('HTTPS fixture requires a literal loopback authority')
        self.broker=broker;self.authority=authority;self.context=context
        self.events=[];self.stopped=False;self.lock=threading.Lock()

    @contextmanager
    def serve(self):
        bridge=self
        class Base(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reject(self,status=403):
                self.send_response(status);self.send_header('Content-Length','0');self.send_header('Connection','close');self.end_headers();self.close_connection=True
            def blocked(self):
                bridge.events.append('BLOCKED');self.reject()
            def setup(self):
                super().setup();self.connection.settimeout(8)
            do_GET=do_HEAD=do_POST=do_PUT=do_DELETE=do_OPTIONS=do_PATCH=do_CONNECT=blocked

        class Inner(Base):
            def forward(self):
                # Origin-form only. Never use caller's Host or absolute URL as an upstream destination.
                if not self.path.startswith('/') or self.path.startswith('//') or self.headers.get_all('Host')!=[bridge.authority] or self.headers.get('Upgrade') or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length','0')!='0':
                    return self.blocked()
                url='https://'+bridge.authority+self.path
                with bridge.lock:
                    if bridge.stopped:return self.blocked()
                    try:bridge.broker._check(url,self.command)
                    except (GuardError,OSError):return self.blocked()
                    try:
                        receipt=bridge.broker.fetch_one(url,self.command)
                        headers={k:v for k,v in receipt.headers if k.lower() in ('content-type','content-disposition','cache-control','retry-after')}
                        if receipt.status in REDIRECTS:headers['location']=bridge.broker.redirect_target(receipt,self.command)
                        bridge.events.append(receipt.status)
                        if receipt.status in (401,403,429):bridge.stopped=True
                    except WaitRequired:
                        bridge.stopped=True;bridge.events.append('DEFERRED');return self.reject(429)
                    except (GuardError,OSError):
                        bridge.stopped=True;return self.blocked()
                self.send_response(receipt.status)
                for k,v in headers.items():self.send_header(k,v)
                self.send_header('Content-Length',str(len(receipt.data)));self.send_header('Connection','close');self.end_headers();self.close_connection=True
                if self.command!='HEAD':self.wfile.write(receipt.data)
            do_GET=do_HEAD=forward

        class Outer(Base):
            def do_CONNECT(self):
                if self.path!=bridge.authority or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length','0')!='0':return self.blocked()
                self.send_response_only(200,'Connection established');self.end_headers();self.wfile.flush();self.close_connection=True
                try:
                    with bridge.context.wrap_socket(self.connection,server_side=True) as secured:
                        # Intentionally one bounded HTTP/1.1 request per CONNECT fixture.
                        Inner(secured,self.client_address,self.server)
                except (ssl.SSLError,OSError):bridge.events.append('TLS_REJECTED')
        server=ThreadingHTTPServer(('127.0.0.1',0),Outer);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield f'http://127.0.0.1:{server.server_port}'
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
