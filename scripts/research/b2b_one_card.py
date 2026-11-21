"""One explicit GET from an isolated renderer. No discovery, writes or downloads.

The operator must coordinate all other B2B callers sharing the designated IP.
The local session stays within the parent broker. Never print its contents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from scripts.research.b2b_guarded_runner import (
    canonical_root,
    private_dir,
    sandbox_renderer,
    single_runner,
    supervise,
)
from scripts.research.b2b_isolated_broker import RendererBroker
from scripts.research.b2b_network_guard import EgressGate, GuardError
from scripts.research.b2b_pilot_preflight import CONSENT, ORIGIN, preflight
from scripts.research.b2b_readonly_broker import ReadOnlyBroker
from scripts.research.b2b_session_policy import ExactScope, cookie_jar, private_json
from src.modules.saas_foundation.commercial_sources import commercial_identity


def manifest_for(card):
    try:platform,_id= commercial_identity(card)
    except (ValueError,TypeError):raise GuardError('Exact reviewed B2B card required') from None
    if platform!='b2bcenter':raise GuardError('Exact reviewed B2B card required')
    return {'schema':1,'organization':'ООО Арвектум','operator_consent':CONSENT,'card':card,'routes':{card:'page'},'confirm_internal_read_only':True}


def run_worker(card,root,*,transport=None,render=sandbox_renderer):
    root=private_dir(root);manifest=manifest_for(card)
    with single_runner(root):
        state=private_json(root/'session.json');preflight(manifest,state)
        scope=ExactScope(ORIGIN,manifest['routes']);gate=EgressGate(private_dir(root/'egress'));jar=cookie_jar(state)
        if transport is None:transport=httpx.HTTPTransport(verify=True,retries=0,trust_env=False,http2=False)
        broker=ReadOnlyBroker(gate,origin=ORIGIN,permitted=scope,cookies=jar,transport=transport)
        bridge=RendererBroker(broker,scope,seconds=40,max_dispatches=1)
        try:
            try:
                with TemporaryDirectory(dir=root,prefix='one-card-') as tmp:
                    result=render(bridge,origin=ORIGIN,card=card,directory=Path(tmp),mode='case-review')
            except (GuardError,OSError,ValueError):result={'state':'RENDERER_REFUSED_OR_INCOMPLETE'}
            return {'state':result.get('state','UNKNOWN'),'external_id':manifest['card'].rsplit('tender-',1)[1][:-1],
                    'upstream_attempts':bridge.dispatched,'http_statuses':bridge.events[:1],
                    'card_id_visible':result.get('card_id_visible') is True,'login_text_seen':result.get('login_text_seen') is True,
                    'visible_controls':[x for x in result.get('visible_controls',[]) if x in ('Позиции','Скачать файлом','Закупочная документация')],
                    'account_identity_verified':False,'session_server_verified':False,'external_submission_allowed':False,
                    'no_download':True,'sandbox_negative_probe':result.get('sandbox_negative_probe') is True}
        finally:broker.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--card');parser.add_argument('--operator-consent');parser.add_argument('--confirm-sole-egress',action='store_true');parser.add_argument('--init-egress',action='store_true');parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    try:
        if sys.platform!='darwin':raise GuardError('macOS designated host required')
        root=private_dir(canonical_root())
        if args.init_egress:
            if args.card or args.worker or args.operator_consent or args.confirm_sole_egress:raise GuardError('Separate initialization required')
            with single_runner(root):
                path=root/'egress';path.mkdir(mode=0o700);EgressGate(private_dir(path)).initialize()
            receipt={'state':'EGRESS_INITIALIZED','first_minute_quarantine':True,'live_network_performed':False}
        elif args.worker:
            payload=json.loads(sys.stdin.read(4097))
            if set(payload)!={'card','consent','confirm_sole_egress'} or payload['consent']!=CONSENT or payload['confirm_sole_egress'] is not True:raise GuardError('Explicit pilot confirmation required')
            receipt=run_worker(payload['card'],root)
        else:
            if args.operator_consent!=CONSENT or not args.confirm_sole_egress:raise GuardError('Explicit operator scope/sole egress confirmation required')
            manifest_for(args.card)
            receipt=supervise([sys.executable,'-m','scripts.research.b2b_one_card','--worker'],{'card':args.card,'consent':CONSENT,'confirm_sole_egress':True},seconds=55)
        print(json.dumps(receipt,ensure_ascii=False));return 0
    except Exception as e:  # noqa: BLE001 -- no cookie values, URLs, or response body in error output
        print(json.dumps({'state':'PILOT_REFUSED','error_type':type(e).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
