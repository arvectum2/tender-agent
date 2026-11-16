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


def test_eds_dedicated_profile_never_reuses_unmarked_or_foreign_profile(tmp_path):
    from scripts.research.b2b_manual_session import dedicated_profile

    root=tmp_path/'private';root.mkdir(mode=0o700);p=root/'eds-profile'
    assert dedicated_profile(p)==p and p.stat().st_mode&0o777==0o700
    assert dedicated_profile(p)==p
    other=root/'ordinary-browser';other.mkdir(mode=0o700)
    with pytest.raises(OSError):dedicated_profile(other)
    link=root/'link';link.symlink_to(p,target_is_directory=True)
    with pytest.raises(GuardError):dedicated_profile(link)
    (p/'.tender-agent-b2b-eds-profile').chmod(0o644)
    with pytest.raises(GuardError):dedicated_profile(p)


def test_supervised_runner_lock_deadline_and_private_receipt(tmp_path):
    import sys
    import time

    from scripts.research.b2b_guarded_runner import single_runner, supervise

    root=tmp_path.resolve()/'canonical';root.mkdir(mode=0o700)
    with single_runner(root), pytest.raises(GuardError,match='Another B2B runner'), single_runner(root):pass
    assert supervise([sys.executable,'-c','import json,sys;json.load(sys.stdin);print(json.dumps({"test":True}))'],{},seconds=3)=={'test':True}
    begin=time.monotonic()
    with pytest.raises(GuardError,match='deadline exceeded'):supervise([sys.executable,'-c','import time;time.sleep(30)'],{},seconds=0.2)
    assert time.monotonic()-begin<4
    with pytest.raises(GuardError,match='Invalid runner receipt'):supervise([sys.executable,'-c','print("not json")'],{},seconds=3)


def test_legacy_b2b_egress_refused_before_transport(monkeypatch):
    from scripts.acceptance import audit_b2bcenter_oct18_primary as audit
    from scripts.ops import b2b_public_current_card_gate as stage
    from scripts.ops import b2bcenter_oct18_primary_watch as watch
    from scripts.procurement_llm import collect_public_market_originals as market
    from scripts.procurement_llm import unified_source_pipeline as unified
    from src.modules.saas_foundation import commercial_capture, commercial_sources

    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected HTTP transport')
    import urllib.request
    monkeypatch.setattr(urllib.request,'urlopen',forbidden);monkeypatch.setattr(urllib.request,'build_opener',forbidden);monkeypatch.setattr(commercial_capture.httpx,'Client',forbidden);monkeypatch.setattr(stage.subprocess,'run',forbidden)
    for fn,arg in ((audit._public_get,card),(watch.fetch_public,card),(market.fetch_original,card),(unified.read_index,unified.B2B_INDEX.format('razrabotka-sajtov')),(commercial_capture.fetch_card,card),(commercial_sources.read_index,'b2bcenter:razrabotka-sajtov')):
        with pytest.raises(ValueError,match='guarded adapter required'):fn(arg)
    assert stage._read_public(card)=={'http_state':'GUARDED_ACCESS_REQUIRED','raw':None}


def test_one_card_worker_enforces_exact_single_get(tmp_path):
    from scripts.research.b2b_manual_session import save_private
    from scripts.research.b2b_network_guard import EgressGate
    from scripts.research.b2b_one_card import manifest_for, run_worker

    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    root=tmp_path.resolve()/'private';root.mkdir(mode=0o700);path=root/'egress';path.mkdir(mode=0o700)
    g=EgressGate(path);g.initialize();s=g._read();s['blocked_until']=s['last_ns'];g._write(s)
    save_private(root/'session.json',{'origins':[],'cookies':[{'name':'session','value':'offline-only','domain':'www.b2b-center.ru','path':'/','expires':-1,'secure':True,'httpOnly':True,'sameSite':'Strict'}]})
    seen=[]
    def request(req):
        assert str(req.url)==card and req.method=='GET'
        assert req.headers['cookie']=='session=offline-only';seen.append(req.method)
        return httpx.Response(200,headers={'content-type':'text/html'},stream=httpx.ByteStream(b'<html>Fixture</html>'))
    def render(bridge,**kwargs):
        for url,method in ((card+'?extra=1','GET'),(card,'HEAD'),(card,'POST')):
            with pytest.raises(GuardError):bridge.fetch(url,method)
        assert bridge.fetch(card,'GET')[0]==200
        with pytest.raises(GuardError):bridge.fetch(card,'GET')
        return {'state':'fixture','card_id_visible':True,'sandbox_negative_probe':True}
    result=run_worker(card,root,transport=httpx.MockTransport(request),render=render)
    assert result['http_statuses']==[200] and result['upstream_attempts']==1 and result['card_id_visible'] and not result['session_server_verified'] and seen==['GET']
    assert 'offline-only' not in json.dumps(result) and len(g._read()['receipts'])==1
    for bad in ('https://workspace.ru/tenders/fixture-1234/',card+'?x=1',card+'#other'):
        with pytest.raises(GuardError):manifest_for(bad)


def test_expired_cookie_omitted_not_renewed_and_inventory_sanitized():
    from scripts.research.b2b_resource_inventory import inventory
    from scripts.research.b2b_session_policy import cookie_jar

    item={'name':'valid','value':'synthetic-only','domain':'www.b2b-center.ru','path':'/','expires':100,'secure':True,'httpOnly':True,'sameSite':'Strict'}
    old={**item,'name':'expired','expires':10}
    jar=cookie_jar({'cookies':[old,item],'origins':[]},now=20)
    assert [c.name for c in jar.jar]==['valid'] and next(iter(jar.jar)).expires==100
    with pytest.raises(GuardError):cookie_jar({'cookies':[old],'origins':[]},now=20)
    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    body=b'<html><script src="/static/a.js"></script><link rel="stylesheet" href="/static/a.css"><script src="https://foreign.invalid/x.js"></script><script src="/secret.js?token=secret"></script><body>4664540</body></html>'
    result=inventory(card,body)
    assert len(result['static_candidates'])==2 and result['omitted_references']==2 and result['card_id_in_visible_text'] and 'secret' not in str(result)


def test_resource_inventory_reuses_strict_evidence_parser():
    from datetime import UTC, datetime

    from scripts.research.b2b_readonly_broker import Receipt
    from scripts.research.b2b_resource_inventory import card_evidence

    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    raw='<html><body><h1>Разработка сайта № 4664540</h1><div>Приём заявок</div><div>до 21.11.2026 06:00, по МСК</div><section>Организатор:<strong>АО ФИКСТУРА</strong></section><a href="/docs/a.pdf">ТЗ</a><script src="https://foreign.invalid/a.js?secret=token"></script></body></html>'.encode()
    r=card_evidence(card,Receipt(200,(),raw,0,card),datetime(2026,11,16,tzinfo=UTC))
    assert r['card_observation']['external_id']=='4664540' and r['attachment_candidate_count']==1 and r['attachment_coverage_complete'] is False
    assert r['foreign_host_counts']=={'foreign.invalid':1} and 'secret' not in str(r)
    bad=raw.replace(b'4664540',b'4664541');r=card_evidence(card,Receipt(200,(),bad,0,card),datetime(2026,11,16,tzinfo=UTC))
    assert r['card_observation'] is None and r['parser_field']=='heading'


def test_partial_card_evidence_does_not_promote_unknown_organizer():
    from datetime import UTC, datetime

    from scripts.research.b2b_readonly_broker import Receipt
    from scripts.research.b2b_resource_inventory import card_evidence

    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    raw=f'<html><head><link rel="canonical" href="{card}"></head><body><h1>Разработка платформы</h1><span>4664540</span><div>Приём заявок</div><div>до 21.11.2026 06:00, по МСК</div><a href="/docs/a.pdf">ТЗ</a></body></html>'.encode()
    r=card_evidence(card,Receipt(200,(),raw,0,card),datetime(2026,11,16,tzinfo=UTC))
    assert r['card_observation'] is None and r['parser_field']=='organizer'
    partial=r['partial_card_observation'];assert partial['external_id']=='4664540' and partial['displayed_deadline']=='2026-11-21T06:00:00+03:00' and partial['organizer_name_literal'] is None
    assert not partial['organizer_verified'] and not partial['account_identity_verified'] and not partial['external_submission_allowed'] and r['attachment_candidate_count']==1
    bad=raw.replace(b'<span>4664540</span>',b'<span hidden>4664540</span>')
    assert 'partial_card_observation' not in card_evidence(card,Receipt(200,(),bad,0,card),datetime(2026,11,16,tzinfo=UTC))


def test_exact_cdn_static_resources_are_credential_free_and_charged(gate):
    from scripts.research.b2b_cdn_resources import ReviewedCardRenderer, references
    from scripts.research.b2b_readonly_broker import Receipt

    g,_clock=gate;card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    js='https://cdn.b2b-center.ru/static/app.js';css='https://cdn.b2b-center.ru/static/app.css'
    raw=f'<html><script src="{js}"></script><link rel="stylesheet" href="{css}"><script src="{js}?token=fixture"></script><script src="https://else.invalid/x.js"></script><script src="https://cdn.b2b-center.ru/api/x"></script></html>'.encode()
    reviewed=references(card,raw);assert reviewed=={js:'script',css:'style'}
    seen=[]
    def handler(req):
        assert 'cookie' not in req.headers and 'authorization' not in req.headers
        seen.append(str(req.url))
        return httpx.Response(200,headers={'content-type':'text/css' if str(req.url)==css else 'application/javascript','set-cookie':'fixture=not-forwarded'},stream=httpx.ByteStream(b'fixture'))
    bridge=ReviewedCardRenderer(card,Receipt(200,(('content-type','text/html'),('content-security-policy',"default-src 'self'"),('set-cookie','secret=fixture')),raw,0,card),g,reviewed,transport_factory=lambda:httpx.MockTransport(handler))
    status,headers,data=bridge.fetch(card,'GET');assert status==200 and data==raw and 'set-cookie' not in headers and 'content-security-policy' in headers
    for url,method in ((card,'GET'),(js,'POST'),(js+'?x=1','GET'),('https://cdn.b2b-center.ru/static/other.js','GET')):
        with pytest.raises(GuardError):bridge.fetch(url,method)
    assert bridge.fetch(js,'GET')[2]==b'fixture' and bridge.fetch(css,'GET')[2]==b'fixture'
    with pytest.raises(GuardError):bridge.fetch(js,'GET')
    assert seen==[js,css] and len(g._read()['receipts'])==2
    with pytest.raises(GuardError):ReviewedCardRenderer(card,Receipt(200,(),raw,0,card),g,{js:'script','https://cdn.b2b-center.ru/static/other.js':'script'})


@pytest.mark.parametrize('mode',['redirect','wrong-mime','oversized'])
def test_cdn_fails_closed_without_redirect_or_repeat(gate,monkeypatch,mode):
    from scripts.research import b2b_cdn_resources as cdn

    g,_=gate;url='https://cdn.b2b-center.ru/static/a.js';seen=[]
    monkeypatch.setattr(cdn,'MAX_ASSET_BYTES',8)
    def handler(req):
        seen.append(str(req.url));assert 'cookie' not in req.headers
        if mode=='redirect':return httpx.Response(302,headers={'location':'https://cdn.b2b-center.ru/static/b.js'})
        return httpx.Response(200,headers={'content-type':'text/html' if mode=='wrong-mime' else 'application/javascript'},stream=httpx.ByteStream(b'123456789' if mode=='oversized' else b'fixture'))
    fetcher=cdn.StaticFetcher(g,{url:'script'},transport_factory=lambda:httpx.MockTransport(handler))
    with pytest.raises(GuardError):fetcher.fetch(url,'GET')
    with pytest.raises(GuardError):fetcher.fetch(url,'GET')
    assert seen==[url] and fetcher.stopped and len(g._read()['receipts'])==1


def test_reviewed_supplemental_cdn_modules_require_unchanged_root_scope(gate):
    from scripts.research.b2b_cdn_resources import ReviewedCardRenderer, references
    from scripts.research.b2b_readonly_broker import Receipt

    g,_=gate;card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    root='https://cdn.b2b-center.ru/mknp/assets/chunk-root.js';dep='https://cdn.b2b-center.ru/mknp/assets/chunk-extra.js'
    data=f'<html><script src="{root}"></script></html>'.encode()
    receipt=Receipt(200,(),data,0,card);review=references(card,data);seen=[]
    def respond(req):
        assert 'cookie' not in req.headers and 'authorization' not in req.headers
        seen.append(str(req.url))
        return httpx.Response(200,headers={'content-type':'application/javascript'},stream=httpx.ByteStream(b'fixture'))
    bridge=ReviewedCardRenderer(card,receipt,g,review,supplemental={dep:'script'},transport_factory=lambda:httpx.MockTransport(respond))
    assert bridge.fetch(dep,'GET')[0]==200 and seen==[dep]
    for bad in ({dep+'?x=1':'script'},{root:'script'},{'https://cdn.b2b-center.ru/api/chunk-extra.js':'script'},{'https://cdn.b2b-center.ru/mknp/assets/chunk-extra.css':'style'}):
        with pytest.raises(GuardError):ReviewedCardRenderer(card,receipt,g,review,supplemental=bad)
    with pytest.raises(GuardError):ReviewedCardRenderer(card,receipt,g,{},supplemental={dep:'script'})


def test_manual_ui_observation_metadata_has_no_sensitive_url_parts():
    from scripts.research.b2b_manual_ui_observation import request_metadata

    r=request_metadata('https://www.b2b-center.ru/profile/private?token=fixture-secret','GET','xhr')
    assert r=={'origin':'www.b2b-center.ru','method':'GET','resource_type':'xhr','query_present':True,'same_origin_reviewable':False}
    assert 'secret' not in str(r) and '/profile' not in str(r)
    r=request_metadata('https://other.invalid/opaque-sensitive-path','POST','fetch')
    assert r['origin']=='other.invalid' and not r['same_origin_reviewable'] and 'opaque-sensitive-path' not in str(r)
    r=request_metadata('https://www.b2b-center.ru/card','GET','document')
    assert r['same_origin_reviewable']
