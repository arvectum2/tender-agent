"""Explicit read-only HTTP broker; transport supplied only by offline acceptance.

Not yet attached to the browser. Every redirect hop is an independent admission;
no implicit redirect/retry/proxy from the HTTP client. Never expose response or
request secrets in error messages or the rate log.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import httpx

from scripts.research.b2b_network_guard import GuardError

MAX_RESPONSE = 25*1024*1024
MAX_REDIRECTS = 5
REDIRECTS = {301,302,303,307,308}


def retry_delay(value, *, wall_clock=time.time):
    if value is None:return 60
    value=value.strip()
    try:
        if value.isascii() and value.isdecimal():return max(60,int(value))
        moment=parsedate_to_datetime(value)
        if moment.tzinfo is None:moment=moment.replace(tzinfo=UTC)
        return max(60,math.ceil(moment.timestamp()-wall_clock()))
    except (ValueError,TypeError,OverflowError):return 60


@dataclass(frozen=True)
class Receipt:
    status: int
    headers: tuple[tuple[str,str],...]
    data: bytes
    redirects: int
    final_url: str


class ReadOnlyBroker:
    def __init__(self,gate,*,origin,permitted,transport,wall_clock=time.time):
        # No default live transport. A separately accepted browser integration
        # must provide the dedicated transport and its egress/timeout guarantees.
        parsed=urlsplit(origin)
        if parsed.scheme not in ('https','http') or not parsed.netloc or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:raise GuardError('Invalid broker origin')
        if parsed.scheme=='http' and parsed.hostname not in ('127.0.0.1','::1','localhost'):raise GuardError('HTTP only for localhost fixture')
        self.origin=(parsed.scheme,parsed.netloc);self.gate=gate;self.permitted=permitted;self.wall_clock=wall_clock
        self.client=httpx.Client(transport=transport,follow_redirects=False,trust_env=False,timeout=httpx.Timeout(10.0),headers={'Accept-Encoding':'identity'})

    def close(self):self.client.close()

    def _check(self,url,method):
        try:
            p=urlsplit(url);normalized=urlsplit(str(httpx.URL(url)))
            if (p.scheme,p.netloc)!=self.origin or (normalized.scheme,normalized.netloc)!=self.origin or p.username or p.password or p.fragment or method not in ('GET','HEAD') or not self.permitted(str(httpx.URL(url)),method):raise ValueError
        except (ValueError,TypeError,httpx.InvalidURL) as exc:raise GuardError('Blocked unapproved HTTP route') from exc

    def fetch(self,url,method='GET'):
        for hop in range(MAX_REDIRECTS+1):
            self._check(url,method)
            def attempt(url=url,hop=hop):
                try:
                    with self.client.stream(method,url,follow_redirects=False) as response:
                        status=response.status_code
                        headers=tuple(response.headers.multi_items())
                        if status==429:
                            return Receipt(status,headers,b'',hop,url),status,retry_delay(response.headers.get('retry-after'),wall_clock=self.wall_clock)
                        if status in REDIRECTS:
                            return Receipt(status,headers,b'',hop,url),status,0
                        if response.headers.get('content-encoding','identity').lower() not in ('','identity'):
                            raise GuardError('Unsupported response encoding')
                        data=bytearray()
                        for part in response.iter_raw():
                            if len(data)+len(part)>MAX_RESPONSE:raise GuardError('Bounded response exceeded')
                            data.extend(part)
                        return Receipt(status,headers,bytes(data),hop,url),status,0
                except httpx.HTTPError:raise GuardError('HTTP transport failed; attempt charged') from None
            result=self.gate.dispatch(attempt,method=method)
            if result.status not in REDIRECTS:return result
            locations=[v for k,v in result.headers if k.lower()=='location']
            if len(locations)!=1 or hop==MAX_REDIRECTS:raise GuardError('Redirect missing, ambiguous or limit exceeded')
            url=urljoin(url,locations[0])
        raise GuardError('Redirect limit exceeded')
