"""One reviewed card and explicitly reviewed static CDN paths, read-only.

Dynamic API requests, other pages, redirects and downloads remain denied.
No browser session cookies or authorization headers are forwarded to CDN.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from scripts.research.b2b_cdn_resources import (
    ReviewedCardRenderer,
    references,
    static_kind,
)
from scripts.research.b2b_guarded_runner import (
    canonical_root,
    private_dir,
    sandbox_renderer,
    single_runner,
    supervise,
)
from scripts.research.b2b_network_guard import EgressGate, GuardError
from scripts.research.b2b_one_card import manifest_for
from scripts.research.b2b_pilot_preflight import CONSENT, ORIGIN, preflight
from scripts.research.b2b_readonly_broker import ReadOnlyBroker
from scripts.research.b2b_session_policy import ExactScope, cookie_jar, private_json


def run(card,reviewed,root,*,transport=None,static_transport_factory=None,render=sandbox_renderer,supplemental=None):
    supplemental={} if supplemental is None else supplemental
    root=private_dir(root);manifest=manifest_for(card)
    if not isinstance(reviewed,dict) or not 1<=len(reviewed)<=32 or any(static_kind(u)!=k for u,k in reviewed.items()):raise GuardError('Exact reviewed static scope required')
    with single_runner(root):
        state=private_json(root/'session.json');preflight(manifest,state);scope=ExactScope(ORIGIN,manifest['routes']);gate=EgressGate(private_dir(root/'egress'))
        broker=ReadOnlyBroker(gate,origin=ORIGIN,permitted=scope,cookies=cookie_jar(state),transport=transport or httpx.HTTPTransport(verify=True,retries=0,trust_env=False,http2=False))
        try:receipt=broker.fetch_one(card)
        finally:broker.close()
        if receipt.status!=200 or not any(k.lower()=='content-type' and v.lower().startswith('text/html') for k,v in receipt.headers):return {'state':'CARD_REFUSED','http_status':receipt.status,'static_attempts':0}
        discovered=references(card,receipt.data)
        if any(discovered.get(u)!=kind for u,kind in reviewed.items()) or (supplemental and reviewed!=discovered):return {'state':'STATIC_SCOPE_CHANGED','static_attempts':0}
        bridge=ReviewedCardRenderer(card,receipt,gate,reviewed,supplemental=supplemental,transport_factory=static_transport_factory,seconds=40)
        try:
            with TemporaryDirectory(dir=root,prefix='cdn-card-') as tmp:
                result=render(bridge,origin=ORIGIN,card=card,directory=Path(tmp),mode='reviewed-cdn')
        except (GuardError,OSError,ValueError,subprocess.TimeoutExpired):result={'state':'RENDERER_REFUSED_OR_INCOMPLETE'}
        return {'state':result.get('state','UNKNOWN'),'http_status':receipt.status,'static_attempts':len(bridge.static.seen),'static_statuses':bridge.static.statuses,'static_bytes':bridge.static.total,'static_stopped':bridge.static.stopped,'blocked_request_classes':{k:v for k,v in result.get('blocked_request_classes',{}).items() if isinstance(k,str) and isinstance(v,int) and 0<=v<=10000},'error_classes':result.get('error_classes',{}),'unreviewed_static_paths':result.get('unreviewed_static_paths',[]),'card_id_visible':result.get('card_id_visible') is True,'visible_controls':[v for v in result.get('visible_controls',[]) if v in ('Позиции','Скачать файлом','Закупочная документация')],'login_text_seen':result.get('login_text_seen') is True,'sandbox_negative_probe':result.get('sandbox_negative_probe') is True,'account_identity_verified':False,'session_server_verified':False,'external_submission_allowed':False,'no_download':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--card');parser.add_argument('--reviewed',type=Path);parser.add_argument('--supplemental',type=Path);parser.add_argument('--operator-consent');parser.add_argument('--confirm-sole-egress',action='store_true');parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    try:
        if args.worker:
            p=json.loads(sys.stdin.read(16385))
            if set(p)!={'card','reviewed','supplemental','consent','confirm_sole_egress'} or p['consent']!=CONSENT or p['confirm_sole_egress'] is not True:raise GuardError('Explicit pilot scope required')
            result=run(p['card'],p['reviewed'],canonical_root(),supplemental=p['supplemental'])
        else:
            if args.operator_consent!=CONSENT or not args.confirm_sole_egress or args.reviewed is None:raise GuardError('Explicit pilot scope required')
            manifest_for(args.card);reviewed=private_json(args.reviewed);supplemental=private_json(args.supplemental) if args.supplemental else {}
            result=supervise([sys.executable,'-m','scripts.research.b2b_cdn_pilot','--worker'],{'card':args.card,'reviewed':reviewed,'supplemental':supplemental,'consent':CONSENT,'confirm_sole_egress':True},seconds=55)
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception as exc:  # noqa: BLE001 -- no source or secret details
        print(json.dumps({'state':'CDN_PILOT_REFUSED','error_type':type(exc).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
