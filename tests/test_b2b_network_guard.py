import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from scripts.research.b2b_network_guard import (
    WINDOW,
    EgressGate,
    GuardError,
    WaitRequired,
)
from scripts.research.b2b_readonly_broker import ReadOnlyBroker, retry_delay


@pytest.fixture
def gate(tmp_path):
    directory=tmp_path/'egress';directory.mkdir(mode=0o700)
    clock=[10*WINDOW]
    g=EgressGate(directory,clock=lambda:clock[0],boot='fixture');g.initialize()
    with pytest.raises(WaitRequired) as exc:g.dispatch(lambda:('bad',200,0),method='GET')
    assert exc.value.seconds==60
    clock[0]+=WINDOW
    return g,clock


def test_shared_rolling_limit_and_persisted_restart(gate):
    g,clock=gate;other=EgressGate(g.directory,clock=g.clock,boot='fixture')
    sent=[];mutex=threading.Lock()
    def attempt():
        with mutex:sent.append(clock[0])
        return 'ok',200,0
    def worker(i):
        try:return (g if i%2 else other).dispatch(attempt,method='GET')
        except WaitRequired:return 'wait'
    with ThreadPoolExecutor(max_workers=12) as pool:out=list(pool.map(worker,range(90)))
    assert out.count('ok')==60 and out.count('wait')==30 and len(sent)==60
    clock[0]+=WINDOW-1
    with pytest.raises(WaitRequired):other.dispatch(attempt,method='GET')
    clock[0]+=1
    assert other.dispatch(attempt,method='GET')=='ok' and len(sent)==61


def test_cooldown_failed_attempt_and_recovery(gate):
    g,clock=gate
    assert g.dispatch(lambda:('limited',429,120),method='GET')=='limited'
    clock[0]+=WINDOW
    with pytest.raises(WaitRequired) as exc:g.dispatch(lambda:None,method='GET')
    assert exc.value.seconds==60
    def fail():raise OSError('secret url')
    clock[0]+=WINDOW
    with pytest.raises(OSError):g.dispatch(fail,method='HEAD')
    state=json.loads(g.state.read_text());assert len(state['events'])==1 and state['receipts'][-1]['status'] is None
    assert 'secret url' not in g.state.read_text()
    state['pending']=True;g._write(state)
    with pytest.raises(WaitRequired) as exc:g.dispatch(lambda:None,method='GET')
    assert exc.value.seconds==60
    clock[0]+=WINDOW
    assert g.dispatch(lambda:('ok',200,0),method='HEAD')=='ok'
    reboot=EgressGate(g.directory,clock=lambda:1,boot='new-boot')
    with pytest.raises(WaitRequired):reboot.dispatch(lambda:None,method='GET')
    g.state.write_text('broken')
    with pytest.raises(GuardError,match='Corrupt'):g.dispatch(lambda:None,method='GET')


def test_redirect_download_background_and_retry_after(gate):
    g,clock=gate;seen=[]
    origin='https://fixture.invalid'
    def handler(request):
        seen.append(request.url.path)
        match request.url.path:
            case '/page':return httpx.Response(302,headers={'Location':'/card'})
            case '/card':return httpx.Response(200,stream=httpx.ByteStream(b'<html>fixture</html>'))
            case '/archive':return httpx.Response(307,headers={'Location':'/file'})
            case '/file':return httpx.Response(200,stream=httpx.ByteStream(b'PK fixture'))
            case '/foreign':return httpx.Response(302,headers={'Location':'https://evil.invalid/'})
            case '/limited':return httpx.Response(429,headers={'Retry-After':'90'})
            case _:return httpx.Response(200,stream=httpx.ByteStream(b'background'))
    allowed={'/page','/card','/archive','/file','/foreign','/limited','/background'}
    broker=ReadOnlyBroker(g,origin=origin,permitted=lambda u,m:httpx.URL(u).path in allowed,transport=httpx.MockTransport(handler))
    try:
        assert broker.fetch(origin+'/page').redirects==1
        assert broker.fetch(origin+'/archive').data==b'PK fixture'
        assert broker.fetch(origin+'/background').data==b'background'
        with pytest.raises(GuardError):broker.fetch(origin+'/foreign')
        assert seen==['/page','/card','/archive','/file','/background','/foreign']
        with pytest.raises(GuardError):broker.fetch(origin+'/card','POST')
        assert broker.fetch(origin+'/limited').status==429
        with pytest.raises(WaitRequired) as exc:broker.fetch(origin+'/background')
        assert exc.value.seconds==90 and len(seen)==7
        state=json.loads(g.state.read_text());assert len(state['events'])==7
        assert 'fixture.invalid' not in g.state.read_text() and '/archive' not in g.state.read_text()
        clock[0]+=90_000_000_000;assert broker.fetch(origin+'/background').status==200
    finally:broker.close()
    moment=datetime(2026,11,16,tzinfo=UTC)
    assert retry_delay(format_datetime(moment+timedelta(seconds=125),usegmt=True),wall_clock=moment.timestamp)==125
    assert retry_delay('invalid')==60


def test_interprocess_limit_and_crash_reservation(gate):
    import subprocess
    import sys

    g,clock=gate
    code='''
import sys
from scripts.research.b2b_network_guard import EgressGate,WaitRequired
from pathlib import Path
g=EgressGate(Path(sys.argv[1]),clock=lambda:int(sys.argv[2]),boot='fixture')
count=0
for _ in range(35):
    try:g.dispatch(lambda:('ok',200,0),method='GET');count+=1
    except WaitRequired:pass
print(count)
'''
    workers=[subprocess.Popen([sys.executable,'-c',code,str(g.directory),str(clock[0])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(3)]
    counts=[]
    for worker in workers:
        out,err=worker.communicate(timeout=10);assert worker.returncode==0,err;counts.append(int(out))
    assert sum(counts)==60
    clock[0]+=WINDOW
    crash='''
import os,sys
from scripts.research.b2b_network_guard import EgressGate
from pathlib import Path
g=EgressGate(Path(sys.argv[1]),clock=lambda:int(sys.argv[2]),boot='fixture')
g.dispatch(lambda:os._exit(71),method='GET')
'''
    result=subprocess.run([sys.executable,'-c',crash,str(g.directory),str(clock[0])],timeout=10,check=False)
    assert result.returncode==71 and json.loads(g.state.read_text())['pending'] is True
    with pytest.raises(WaitRequired) as e:g.dispatch(lambda:('bad',200,0),method='GET')
    assert e.value.seconds==60
    clock[0]+=WINDOW;assert g.dispatch(lambda:('ok',200,0),method='GET')=='ok'


def test_real_loopback_redirect_and_download(gate):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    g,_clock=gate;seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            seen.append(self.path)
            if self.path=='/card':
                self.send_response(302);self.send_header('Location','/file');self.send_header('Content-Length','0');self.end_headers()
            elif self.path=='/file':
                data=b'PK offline fixture';self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            else:
                self.send_response(429);self.send_header('Retry-After','75');self.send_header('Content-Length','0');self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    broker=ReadOnlyBroker(g,origin=origin,permitted=lambda u,m:httpx.URL(u).path in ('/card','/file','/limited'),transport=httpx.HTTPTransport(retries=0,trust_env=False))
    try:
        result=broker.fetch(origin+'/card');assert result.data==b'PK offline fixture' and result.redirects==1
        assert broker.fetch(origin+'/limited').status==429
        with pytest.raises(WaitRequired) as err:broker.fetch(origin+'/card')
        assert err.value.seconds==75 and seen==['/card','/file','/limited']
        assert len(json.loads(g.state.read_text())['events'])==3
    finally:broker.close();server.shutdown();server.server_close();thread.join(timeout=3)


def test_staggered_windows_charge_failed_attempts(gate):
    g,clock=gate;sent=[]
    def send():sent.append(clock[0]);return 'ok',200,0
    start=clock[0]
    for i in range(60):
        clock[0]=start+i*500_000_000;assert g.dispatch(send,method='GET')=='ok'
    clock[0]=start+WINDOW-1
    with pytest.raises(WaitRequired):g.dispatch(send,method='GET')
    clock[0]=start+WINDOW
    assert g.dispatch(send,method='GET')=='ok'
    with pytest.raises(WaitRequired):g.dispatch(send,method='GET')
    clock[0]+=500_000_000
    assert g.dispatch(send,method='HEAD')=='ok'
    assert len(sent)==62 and all(sum(t-WINDOW<s<=t for s in sent)<=60 for t in sent)
