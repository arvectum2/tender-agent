"""Exact first-party static references and credential-free scoped resource fetch.

Only references present in a reviewed card HTML qualify. No query, redirect,
API discovery or scope enlargement based on script execution.
"""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from scripts.research.b2b_isolated_broker import RendererBroker
from scripts.research.b2b_network_guard import GuardError
from scripts.research.b2b_readonly_broker import ReadOnlyBroker

CDN='https://cdn.b2b-center.ru'
MAX_ASSETS=32
SUPPLEMENTAL=re.compile(r'/mknp/assets/chunk-[A-Za-z0-9_-]{1,100}\.js\Z')
MAX_ASSET_BYTES=8*1024*1024
MAX_TOTAL_BYTES=32*1024*1024
PATH=re.compile(r'/[A-Za-z0-9_./~-]{1,240}\.(?:m?js|css)\Z',re.IGNORECASE)
MIME_JS={'application/javascript','text/javascript','application/x-javascript','application/ecmascript','text/ecmascript'}


def static_kind(url):
    p=urlsplit(url)
    if (p.scheme,p.netloc)!=('https','cdn.b2b-center.ru') or p.query or p.fragment or not PATH.fullmatch(p.path) or any(v in ('','.','..') for v in p.path[1:].split('/')) or str(httpx.URL(url))!=url:
        raise GuardError('Unreviewed static URL')
    return 'style' if p.path.lower().endswith('.css') else 'script'


class ReferenceParser(HTMLParser):
    def __init__(self,card):
        super().__init__(convert_charrefs=True);self.card=card;self.result={};self.examined=0

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='base' and 'href' in a:raise GuardError('Base URL unsupported')
        if tag not in ('script','link'):return
        if len(a)!=len(attrs):return
        rel=(a.get('rel') or '').lower().split()
        if tag=='link' and not ('stylesheet' in rel or 'modulepreload' in rel or ('preload' in rel and a.get('as') in ('script','style'))):return
        self.examined+=1
        if self.examined>200:raise GuardError('Reference scan budget exceeded')
        src=a.get('src') if tag=='script' else a.get('href')
        if not isinstance(src,str) or any(ord(c)<33 or ord(c)>126 for c in src):return
        try:url=urljoin(self.card,src);kind=static_kind(url)
        except (GuardError,ValueError,TypeError,httpx.InvalidURL):return
        expected='script' if tag=='script' or 'modulepreload' in rel or a.get('as')=='script' else 'style'
        if kind==expected:self.result[url]=kind
        if len(self.result)>MAX_ASSETS:raise GuardError('Static reference budget exceeded')


def references(card,raw):
    if not 0<len(raw)<=2*1024*1024:raise GuardError('Bounded HTML required')
    parser=ReferenceParser(card);parser.feed(raw.decode('utf-8',errors='strict'));parser.close();return parser.result


class StaticFetcher:
    def __init__(self,gate,reviewed,*,transport_factory=None):
        if not 1<=len(reviewed)<=MAX_ASSETS or any(static_kind(u)!=k for u,k in reviewed.items()):raise GuardError('Explicit reviewed static scope required')
        self.gate=gate;self.reviewed=dict(reviewed);self.total=0;self.seen=set();self.statuses=[];self.stopped=False;self.transport_factory=transport_factory or (lambda:httpx.HTTPTransport(verify=True,retries=0,trust_env=False,http2=False))

    def fetch(self,url,method):
        if self.stopped or method!='GET' or url not in self.reviewed or url in self.seen:raise GuardError('Static scope blocked')
        remaining=min(MAX_ASSET_BYTES,MAX_TOTAL_BYTES-self.total)
        if remaining<=0:raise GuardError('Static byte budget exhausted')
        self.seen.add(url)
        # One fresh cookie-free client per request; response Set-Cookie cannot
        # affect any later request. No redirects or custom caller headers.
        broker=ReadOnlyBroker(self.gate,origin=CDN,permitted=lambda u,m:u==url and m=='GET',transport=self.transport_factory(),max_response_bytes=remaining)
        try:
            r=broker.fetch_one(url);self.statuses.append(r.status)
            if r.status!=200:raise GuardError('Static response refused')
            mime=next((v.split(';',1)[0].strip().lower() for k,v in r.headers if k.lower()=='content-type'),'')
            valid=mime=='text/css' if self.reviewed[url]=='style' else mime in MIME_JS
            if not valid or not 0<len(r.data)<=MAX_ASSET_BYTES or self.total+len(r.data)>MAX_TOTAL_BYTES:raise GuardError('Static MIME or size refused')
            self.total+=len(r.data)
            headers={k:v for k,v in r.headers if k.lower() in ('content-type','access-control-allow-origin','cross-origin-resource-policy','x-content-type-options')}
            return r.status,headers,r.data
        except (GuardError,OSError):self.stopped=True;raise
        finally:broker.close()


class ReviewedCardRenderer(RendererBroker):
    """Serve a captured card once and exact reviewed static assets only."""
    def __init__(self,card,receipt,gate,reviewed,*,supplemental=None,transport_factory=None,seconds=40):
        if receipt.status!=200 or receipt.final_url!=card:raise GuardError('Exact card receipt required')
        actual=references(card,receipt.data)
        if any(actual.get(u)!=kind for u,kind in reviewed.items()):raise GuardError('Static scope no longer matches card')
        supplemental={} if supplemental is None else supplemental
        # Explicit prior browser observations only; never discover and fetch in one
        # step. Require all current root references unchanged before extending scope.
        if not isinstance(supplemental,dict) or len(supplemental)>8:raise GuardError('Invalid supplemental scope')
        if supplemental and (reviewed!=actual or any(u in actual or k!='script' or static_kind(u)!='script' or not SUPPLEMENTAL.fullmatch(urlsplit(u).path) for u,k in supplemental.items())):raise GuardError('Unreviewed supplemental module')
        super().__init__(None,None,seconds=seconds)
        self.card=card;self.receipt=receipt;self.page_served=False
        self.static=StaticFetcher(gate,{**reviewed,**supplemental},transport_factory=transport_factory)

    def fetch(self,url,method):
        with self.lock:
            if self.stopped or time.monotonic()>=self.deadline or method!='GET':raise GuardError('Renderer blocked')
            if url==self.card and not self.page_served:
                self.page_served=True
                # Preserve origin CSP, do not weaken script or frame policy.
                allowed={'content-type','content-security-policy','content-security-policy-report-only','x-content-type-options','x-frame-options','referrer-policy'}
                headers={k:v for k,v in self.receipt.headers if k.lower() in allowed}
                return 200,headers,self.receipt.data
            if url not in self.static.reviewed or url in self.static.seen:raise GuardError('Unreviewed or repeated static request')
            try:return self.static.fetch(url,method)
            except (GuardError,OSError):self.stopped=True;raise
