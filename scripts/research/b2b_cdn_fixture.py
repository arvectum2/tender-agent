"""Reproducible real-Chrome offline acceptance for reviewed CDN resources."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from scripts.research.b2b_cdn_resources import ReviewedCardRenderer, references
from scripts.research.b2b_guarded_runner import sandbox_renderer
from scripts.research.b2b_network_guard import EgressGate
from scripts.research.b2b_readonly_broker import Receipt


def main():
    card='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
    js='https://cdn.b2b-center.ru/static/app.js';css='https://cdn.b2b-center.ru/static/app.css'
    raw=f'<html><head><link rel="stylesheet" href="{css}"></head><body><h1>Fixture 4664540</h1><script src="{js}"></script></body></html>'.encode()
    with TemporaryDirectory() as tmp:
        root=Path(tmp).resolve();state=root/'egress';state.mkdir(mode=0o700);g=EgressGate(state);g.initialize();s=g._read();s['blocked_until']=s['last_ns'];g._write(s)
        seen=[]
        def handle(req):
            assert 'cookie' not in req.headers and 'authorization' not in req.headers
            url=str(req.url);seen.append(url)
            if url==js:return httpx.Response(200,headers={'content-type':'application/javascript'},stream=httpx.ByteStream("document.body.append(Object.assign(document.createElement('button'),{textContent:'Позиции'}));fetch('/unreviewed-api').catch(()=>0);".encode()))
            assert url==css
            return httpx.Response(200,headers={'content-type':'text/css'},stream=httpx.ByteStream(b'body{color:green}'))
        bridge=ReviewedCardRenderer(card,Receipt(200,(('content-type','text/html; charset=utf-8'),),raw,0,card),g,references(card,raw),transport_factory=lambda:httpx.MockTransport(handle))
        r=sandbox_renderer(bridge,origin='https://www.b2b-center.ru',card=card,directory=root,mode='reviewed-cdn')
        assert r['card_id_visible'] and r['sandbox_negative_probe'] and 'Позиции' in r['visible_controls']
        assert set(seen)=={js,css} and len(g._read()['receipts'])==2
        assert r['blocked_request_classes'].get('card-origin|fetch|GET',0)>=1
        print(json.dumps({'state':'OFFLINE_CDN_ACCEPTANCE','charged_static_requests':len(seen),'card_id_visible':True,'unreviewed_api_requests':0,'blocked_request_classes':r['blocked_request_classes']},ensure_ascii=False))


if __name__=='__main__':main()
