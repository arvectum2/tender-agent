"""Offline-only Playwright bridge. No live domain or credential support.

Chromium is routed to an explicit HTTP-only local proxy even for loopback.
Every permitted HTTP hop is forwarded via the broker and charged; no CONNECT
or other tunnels. This is a browser
configuration acceptance fixture, not an operating-system network sandbox.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from scripts.research.b2b_network_guard import GuardError, WaitRequired
from scripts.research.b2b_readonly_broker import REDIRECTS


@contextmanager
def deny_proxy():
    """No forwarding, no DNS, no private URLs recorded."""
    attempts=[]
    class Reject(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reject(self):
            attempts.append(self.command);self.send_response(403);self.send_header('Content-Length','0');self.send_header('Connection','close');self.end_headers();self.close_connection=True
        do_GET=do_HEAD=do_POST=do_PUT=do_DELETE=do_OPTIONS=do_PATCH=do_CONNECT=reject
    server=ThreadingHTTPServer(('127.0.0.1',0),Reject);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',attempts
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


def launch_options(proxy):
    return {'channel':'chrome','headless':True,'timeout':8000,'proxy':{'server':proxy,'bypass':'<-loopback>'},'args':['--disable-quic','--disable-background-networking','--disable-sync','--disable-component-update','--no-first-run','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--force-webrtc-ip-handling-policy=disable_non_proxied_udp']}


class OfflineBrowserBridge:
    def __init__(self,broker):
        scheme,host=broker.origin
        if scheme!='http' or urlsplit(f'http://{host}').hostname!='127.0.0.1':raise GuardError('Bridge is restricted to an offline loopback fixture')
        self.broker=broker;self.events=[];self.stopped=False
        self._lock=threading.Lock()

    @contextmanager
    def serve(self):
        bridge=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reject(self,status=403):
                self.send_response(status);self.send_header('Content-Length','0');self.send_header('Connection','close');self.end_headers();self.close_connection=True
            def blocked(self):
                bridge.events.append('BLOCKED');self.reject()
            def forward(self):
                # Absolute-form requests only. No CONNECT, tunnel, streaming,
                # request body, upgrade or caller-supplied credentials.
                if self.headers.get('Upgrade') or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length','0')!='0':return self.blocked()
                with bridge._lock:
                    if bridge.stopped:return self.blocked()
                    try:
                        bridge.broker._check(self.path,self.command)
                    except (GuardError,OSError):return self.blocked()
                    try:
                        receipt=bridge.broker.fetch_one(self.path,self.command)
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
            do_POST=do_PUT=do_DELETE=do_OPTIONS=do_PATCH=do_CONNECT=blocked
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield f'http://127.0.0.1:{server.server_port}'
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
