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


def test_offline_browser_proxy_only_approved_routes(gate):
    from scripts.research.b2b_browser_bridge import OfflineBrowserBridge

    g,_clock=gate;seen=[];origin='http://127.0.0.1:49111'
    def handler(request):
        seen.append(request.url.path)
        if request.url.path=='/redirect':return httpx.Response(302,headers={'Location':'/file'})
        if request.url.path=='/foreign':return httpx.Response(302,headers={'Location':'https://outside.invalid/'})
        return httpx.Response(200,stream=httpx.ByteStream(b'fixture'))
    broker=ReadOnlyBroker(g,origin=origin,permitted=lambda url,method:httpx.URL(url).path in ('/redirect','/file','/foreign'),transport=httpx.MockTransport(handler))
    try:
        bridge=OfflineBrowserBridge(broker)
        with bridge.serve() as proxy, httpx.Client(proxy=proxy,trust_env=False,follow_redirects=True,timeout=3) as client:
            assert client.get(origin+'/redirect').content==b'fixture'
            assert client.get(origin+'/unapproved').status_code==403
            assert client.post(origin+'/file',content=b'x').status_code==403
            assert client.get('http://outside.invalid/').status_code==403
            with pytest.raises(httpx.ProxyError):client.get('https://outside.invalid/')
            assert client.get(origin+'/foreign').status_code==403
            assert bridge.stopped and client.get(origin+'/file').status_code==403
        assert seen==['/redirect','/file','/foreign']
        assert len(json.loads(g.state.read_text())['receipts'])==3
    finally:broker.close()
    other=ReadOnlyBroker(g,origin='https://outside.invalid',permitted=lambda *_:True,transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(GuardError):OfflineBrowserBridge(other)
    finally:other.close()


def test_tls_fixture_proxy_rejects_nonloopback_and_connect(gate):
    import ssl

    from scripts.research.b2b_https_fixture_bridge import OfflineTLSBridge

    g,_clock=gate
    def no_network(request):raise AssertionError('Unexpected upstream request')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    for origin in ('http://127.0.0.1:49111','https://outside.invalid','https://localhost:49111','https://127.0.0.1'):
        broker=ReadOnlyBroker(g,origin=origin,permitted=lambda *_:True,transport=httpx.MockTransport(no_network))
        try:
            with pytest.raises(GuardError):OfflineTLSBridge(broker,context=context)
        finally:broker.close()
    broker=ReadOnlyBroker(g,origin='https://127.0.0.1:49111',permitted=lambda *_:True,transport=httpx.MockTransport(no_network))
    try:
        bridge=OfflineTLSBridge(broker,context=context)
        with bridge.serve() as proxy,httpx.Client(proxy=proxy,trust_env=False,timeout=3) as client:
            assert client.get('http://127.0.0.1:49111/').status_code==403
            with pytest.raises(httpx.ProxyError):client.get('https://outside.invalid/')
            with pytest.raises(httpx.ProxyError):client.get('https://127.0.0.1:49112/')
        assert bridge.events==['BLOCKED']*3 and json.loads(g.state.read_text())['receipts']==[]
    finally:broker.close()


def test_private_session_and_exact_route_scope(tmp_path):
    from scripts.research.b2b_session_policy import (
        HOST,
        ExactScope,
        cookie_jar,
        private_json,
    )

    url='https://'+HOST;card=url+'/app/market-next/fixture/tender-4664540/'
    scope=ExactScope(url,{card:'page',url+'/fixture.zip':'archive'})
    assert scope(card,'GET') and not scope(card,'POST') and not scope(card+'?x=1','GET') and not scope(card+'x','GET')
    for routes in ({'https://outside.invalid/':'page'},{card:'#unknown'},{card+'#x':'page'}):
        with pytest.raises(GuardError):ExactScope(url,routes)
    item={'name':'session','value':'synthetic-only','domain':'.b2b-center.ru','path':'/app/','expires':-1,'secure':True,'httpOnly':True,'sameSite':'Strict'}
    state={'cookies':[item],'origins':[]};p=tmp_path/'session.json';p.write_text(json.dumps(state));p.chmod(0o600)
    jar=cookie_jar(private_json(p),now=1)
    cookie=next(iter(jar.jar));assert cookie.secure and cookie.domain==HOST and not cookie.domain_specified
    req=httpx.Request('GET',card);jar.set_cookie_header(req);assert req.headers['cookie']=='session=synthetic-only'
    for bad_url in ('https://outside.invalid/app/x',url+'/not-app','http://'+HOST+'/app/x'):
        req=httpx.Request('GET',bad_url);jar.set_cookie_header(req);assert 'cookie' not in req.headers
    for bad in ({**item,'domain':'outside.invalid'},{**item,'secure':False},{**item,'expires':0},{**item,'partitionKey':'nope'},{**item,'value':'x\r\ny'}):
        with pytest.raises(GuardError):cookie_jar({'cookies':[bad],'origins':[]},now=1)
    with pytest.raises(GuardError):cookie_jar({'cookies':[item,item],'origins':[]},now=1)
    with pytest.raises(GuardError):cookie_jar({'cookies':[item],'origins':[{'origin':url}]},now=1)
    p.chmod(0o644)
    with pytest.raises(GuardError):private_json(p)
    p.chmod(0o600);link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(OSError):private_json(link)


def test_renderer_broker_exact_routes_and_private_ipc(gate):
    from scripts.research.b2b_isolated_broker import RendererBroker
    from scripts.research.b2b_session_policy import ExactScope

    g,_clock=gate;origin='https://127.0.0.1:49111';seen=[]
    scope=ExactScope(origin,{origin+'/page':'page',origin+'/archive':'archive',origin+'/file':'archive',origin+'/badarchive':'archive'})
    def handle(request):
        seen.append(request.url.path)
        if request.url.path=='/archive':return httpx.Response(307,headers={'location':'/file'})
        if request.url.path=='/badarchive':return httpx.Response(302,headers={'location':'/page'})
        if request.url.path=='/file':return httpx.Response(200,headers={'content-disposition':'attachment; filename="fixture.zip"'},stream=httpx.ByteStream(b'PK fixture'))
        return httpx.Response(200,stream=httpx.ByteStream(b'page'))
    broker=ReadOnlyBroker(g,origin=origin,permitted=scope,transport=httpx.MockTransport(handle))
    try:
        adapter=RendererBroker(broker,scope)
        with adapter.serve() as port,httpx.Client(trust_env=False,timeout=3) as client:
            endpoint=f'http://127.0.0.1:{port}/fetch';payload={'url':origin+'/page','method':'GET'}
            assert client.post(endpoint,json=payload).status_code==403 and seen==[]
            headers={'Authorization':'Bearer '+adapter.token}
            assert client.post(endpoint,json={**payload,'url':origin+'/unknown'},headers=headers).status_code==403 and seen==[]
            assert client.post(endpoint,json={**payload,'method':'POST'},headers=headers).status_code==403 and seen==[]
            assert client.post(endpoint,json=payload,headers=headers).content==b'page'
            assert client.post(endpoint,json={**payload,'url':origin+'/archive'},headers=headers).content==b'PK fixture'
            assert seen==['/page','/archive','/file']
            assert client.post(endpoint,json={**payload,'url':origin+'/badarchive'},headers=headers).status_code==403
            assert adapter.stopped and seen==['/page','/archive','/file','/badarchive']
            assert client.post(endpoint,json=payload,headers=headers).status_code==403
        assert len(json.loads(g.state.read_text())['receipts'])==4 and adapter.token not in g.state.read_text()
    finally:broker.close()


def test_pilot_preflight_is_explicit_and_does_not_activate():
    from scripts.research.b2b_pilot_preflight import CONSENT, ORIGIN, preflight

    card=ORIGIN+'/app/market-next/fixture/tender-4664540/'
    manifest={'schema':1,'organization':'ООО Арвектум','operator_consent':CONSENT,'card':card,'routes':{card:'page'},'confirm_internal_read_only':True}
    session={'cookies':[{'name':'session','value':'synthetic-only','domain':'www.b2b-center.ru','path':'/','expires':-1,'secure':True,'httpOnly':True,'sameSite':'Strict'}],'origins':[]}
    receipt=preflight(manifest,session);assert receipt['state']=='LOCAL_INPUT_VALIDATED_LIVE_DISABLED' and receipt['external_id']=='4664540' and receipt['account_identity_verified'] is False and receipt['live_network_performed'] is False and 'synthetic-only' not in json.dumps(receipt)
    with pytest.raises(GuardError):preflight({**manifest,'operator_consent':'other'},session)
    with pytest.raises(GuardError):preflight({**manifest,'confirm_internal_read_only':False},session)
    with pytest.raises(GuardError):preflight({**manifest,'routes':{card:'page',ORIGIN+'/other':'page'}},session)


def test_manual_session_capture_filters_and_never_overwrites(tmp_path):
    from scripts.research.b2b_manual_session import save_private, select_cookie_state
    from scripts.research.b2b_session_policy import private_json

    item={'name':'session','value':'synthetic-only','domain':'www.b2b-center.ru','path':'/','expires':-1,'secure':True,'httpOnly':True,'sameSite':'Strict'}
    selected=select_cookie_state([item,{**item,'name':'analytics','secure':False},{**item,'domain':'other.invalid'}]);assert selected=={'cookies':[item],'origins':[]}
    root=tmp_path/'private';root.mkdir(mode=0o700);p=root/'session.json';save_private(p,selected);assert p.stat().st_mode&0o777==0o600 and private_json(p)==selected
    with pytest.raises(FileExistsError):save_private(p,selected)
    with pytest.raises(GuardError):select_cookie_state([{**item,'domain':'outside.invalid'}])
