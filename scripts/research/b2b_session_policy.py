"""Exact reviewed scope and local HTTPS-only cookie input; no automatic login.

Live activation remains separate. Never print cookie values or reviewed URLs with
query secrets. A manifest is positive scope, not proof of operator permission.
"""
from __future__ import annotations

import json
import math
import os
import stat
import time
from http.cookiejar import Cookie
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from scripts.research.b2b_network_guard import GuardError

HOST='www.b2b-center.ru'
MAX_STATE=1024*1024


def private_json(path):
    fd=os.open(Path(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1 or not 0<info.st_size<=MAX_STATE:raise GuardError('Private bounded regular session file required')
        raw=f.read(MAX_STATE+1)
    if len(raw)>MAX_STATE:raise GuardError('Session size limit')
    try:return json.loads(raw)
    except (ValueError,UnicodeError):raise GuardError('Invalid session data') from None


def cookie_jar(state,*,now=None):
    """Import only ordinary secure B2B cookies from a dedicated local state.

    Origin/localStorage tokens and partitioned cookies deliberately unsupported.
    Uncertain or expired credentials are rejected, not silently reconstructed.
    """
    now=time.time() if now is None else now
    if not isinstance(state,dict) or set(state)!={'cookies','origins'} or state['origins']!=[] or not isinstance(state['cookies'],list) or not 1<=len(state['cookies'])<=100:raise GuardError('Dedicated cookie-only session required')
    jar=httpx.Cookies();seen=set()
    for c in state['cookies']:
        if not isinstance(c,dict) or not {'name','value','domain','path','expires','secure','httpOnly','sameSite'}<=set(c) or set(c)-{'name','value','domain','path','expires','secure','httpOnly','sameSite'}:raise GuardError('Unsupported cookie metadata')
        name=c['name'];value=c['value'];domain=c['domain'];path=c['path'];expires=c['expires']
        if not isinstance(name,str) or not name or len(name)>256 or any(ord(x)<33 or ord(x)>126 or x in '=;, ' for x in name) or not isinstance(value,str) or not value or len(value)>8192 or any(ord(x)<33 or ord(x)>126 or x in ';,' for x in value):raise GuardError('Invalid cookie')
        if domain not in (HOST,'b2b-center.ru','.b2b-center.ru','.'+HOST) or not isinstance(path,str) or not path.startswith('/') or len(path)>512 or any(ord(x)<32 or ord(x)>126 for x in path) or c['secure'] is not True or type(c['httpOnly']) is not bool or c['sameSite'] not in ('Strict','Lax','None'):raise GuardError('Unsupported cookie scope')
        if type(expires) not in (int,float) or not math.isfinite(expires) or expires!=-1 and (expires<=now or expires>253402300799):raise GuardError('Invalid or expired cookie')
        # Use exact host only, even for a broader source cookie. No credentials sent to other hosts.
        identity=(name,path)
        if identity in seen:raise GuardError('Ambiguous cookie identity')
        seen.add(identity)
        jar.jar.set_cookie(Cookie(0,name,value,None,False,HOST,False,False,path,True,True,None if expires==-1 else int(expires),expires==-1,None,None,{'HttpOnly':c['httpOnly'],'SameSite':c['sameSite']},False))
    return jar


class ExactScope:
    def __init__(self,origin,routes):
        p=urlsplit(origin)
        if p.scheme!='https' or p.path or p.query or p.fragment or p.username or p.password or (p.netloc!=HOST and (p.hostname!='127.0.0.1' or p.port is None or p.netloc!=f'127.0.0.1:{p.port}')):raise GuardError('Unsupported HTTPS origin')
        if not isinstance(routes,dict) or not 1<=len(routes)<=300:raise GuardError('Bounded reviewed URLs required')
        self.origin=origin;self.routes={}
        for url,kind in routes.items():
            if not isinstance(url,str) or len(url)>2048 or kind not in ('page','asset','archive') or any(ord(x)<33 or ord(x)>126 for x in url):raise GuardError('Invalid reviewed route')
            u=urlsplit(url)
            if (u.scheme,u.netloc)!=(p.scheme,p.netloc) or u.fragment or u.username or u.password or not u.path.startswith('/') or str(httpx.URL(url))!=url:raise GuardError('Noncanonical or foreign route')
            self.routes[url]=kind
    def __call__(self,url,method):return method in ('GET','HEAD') and url in self.routes
    def kind(self,url):return self.routes.get(url)
