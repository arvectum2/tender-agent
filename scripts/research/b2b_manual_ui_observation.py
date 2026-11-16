"""User-driven UI observation in the already dedicated Chrome profile.

No programmatic navigation/click/login, no credential inspection, no request
headers/bodies/query values, no automatic route approval or upstream replay.
Run locally while all B2B automated callers are stopped. This is manual browser
use, not a rate-limited automated pilot.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from urllib.parse import urlsplit

from scripts.research.b2b_guarded_runner import (
    canonical_root,
    private_dir,
    single_runner,
)
from scripts.research.b2b_manual_session import dedicated_profile
from scripts.research.b2b_network_guard import GuardError
from scripts.research.b2b_one_card import manifest_for
from scripts.research.commercial_document_acquisition import observe

MAX_RECORDS=200
SAFE_PATH=re.compile(r'/[A-Za-z0-9_./~-]{1,240}\Z')
SAFE_HOST=re.compile(r'[a-z0-9.-]{1,253}\Z')


def request_metadata(url,method,resource_type):
    p=urlsplit(url)
    host=p.netloc if p.scheme=='https' and SAFE_HOST.fullmatch(p.netloc or '') else 'other'
    category=resource_type if resource_type in ('document','script','stylesheet','xhr','fetch','image','font','media','websocket','eventsource') else 'other'
    method=method if method in ('GET','HEAD','POST') else 'other'
    # No query parameters, headers, body or opaque URL for external requests.
    return {'origin':host,'method':method,'resource_type':category,
            'query_present':bool(p.query),'same_origin_reviewable':host=='www.b2b-center.ru' and method=='GET' and not p.query and not p.fragment and SAFE_PATH.fullmatch(p.path) is not None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card',required=True)
    args=parser.parse_args()
    if sys.platform!='darwin' or not sys.stdin.isatty() or not sys.stdout.isatty():parser.error('Interactive local Mac mini terminal required')
    manifest_for(args.card)
    from playwright.sync_api import sync_playwright
    try:
        root=private_dir(canonical_root())
        if not (root/'password-profile'/'.tender-agent-b2b-eds-profile').is_file():raise GuardError('Existing dedicated profile required')
        profile=dedicated_profile(root/'password-profile')
        with single_runner(root),sync_playwright() as driver:
            ctx=driver.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,timeout=8000,ignore_https_errors=False,chromium_sandbox=True)
            try:
                counts=Counter();count=[0]
                def note(request):
                    if count[0]>=MAX_RECORDS:return
                    count[0]+=1
                    row=request_metadata(request.url,request.method,request.resource_type)
                    counts[(row['origin'],row['method'],row['resource_type'],row['query_present'])]+=1
                ctx.on('request',note)
                page=ctx.new_page()
                print('Откройте вручную указанную карточку в новом окне. Проверьте, что доступен кабинет ООО «Арвектум». Не подавайте заявку и не подписывайте документы.')
                print(args.card)
                print('После загрузки карточки и визуальной проверки кабинета введите ARVECTUM. Пароль вводится только в браузере, если потребуется.')
                # Pump Playwright events while the operator interacts; no automatic navigation.
                import select
                while not select.select([sys.stdin],[],[],0)[0]:page.wait_for_timeout(250)
                if sys.stdin.readline().strip()!='ARVECTUM':raise GuardError('Manual confirmation missing')
                candidates=[p for p in ctx.pages if p.url==args.card]
                if len(candidates)!=1:raise GuardError('Exact visible card required')
                result=observe(candidates[0],args.card,authenticated=False)
                report={'state':'MANUAL_UI_REVIEW','owner_account_attested':True,'account_identity_independently_verified':False,'exact_card_url_observed':True,'visible_controls':result['visible_controls'],'request_classes':[{'origin':host,'method':method,'resource_type':kind,'query_present':query,'count':n} for (host,method,kind,query),n in sorted(counts.items())],'metadata_truncated':count[0]>=MAX_RECORDS,'automatic_route_approval':False,'external_submission_allowed':False}
                path=root/'manual-ui-observation.json'
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'w') as f:json.dump(report,f,ensure_ascii=False)
                print(json.dumps({'state':report['state'],'observed_request_classes':len(report['request_classes']),'visible_controls':report['visible_controls']},ensure_ascii=False))
            finally:ctx.close()
    except Exception as exc:  # noqa: BLE001 -- never print browser error contents
        print('Manual observation refused: '+type(exc).__name__);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
