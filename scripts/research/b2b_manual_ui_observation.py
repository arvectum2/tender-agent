"""User-driven UI observation in the already dedicated Chrome profile.

No programmatic navigation/click/login, no credential inspection, no request
headers/bodies/query values, no automatic route approval or upstream replay.
Run locally while all B2B automated callers are stopped. This is manual browser
use, not a rate-limited automated pilot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
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
from scripts.research.commercial_document_acquisition import (
    B2B_FLOW,
    _unique_visible,
    plan,
)

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


def manual_card_match(expected,actual):
    """Compare *observed* browser location only. Never authorize network URLs."""
    manifest_for(expected)
    try:
        a=urlsplit(actual);e=urlsplit(expected)
        return a.scheme=='https' and a.netloc==e.netloc and a.path.rstrip('/')==e.path.rstrip('/')
    except (TypeError,ValueError):
        return False


def manual_observe(page,card):
    if not manual_card_match(card,page.url):raise GuardError('Manual card path mismatch')
    identifier=card.rsplit('tender-',1)[-1].rstrip('/')
    body=page.locator('body').inner_text(timeout=1500)
    if not 0<len(body)<=500000 or not re.search(r'(?<![0-9])'+re.escape(identifier)+r'(?![0-9])',body):
        raise GuardError('Visible exact procurement number required')
    controls=[]
    for label in B2B_FLOW:
        try:_unique_visible(page,label)
        except ValueError:continue
        controls.append(label)
    if not manual_card_match(card,page.url):raise GuardError('Manual navigation changed')
    result=plan(card,body,controls,authenticated=False)
    if result['state']=='ACCESS_CHALLENGE':raise GuardError('Manual access challenge')
    return {'exact_card_path_observed':True,'card_id_visible':True,'url_query_present':bool(urlsplit(page.url).query),
            'external_id':identifier,'visible_controls':controls,'body_sha256':hashlib.sha256(body.encode()).hexdigest()}


def write_receipt(path,report,*,replace=False):
    """Atomic, owner-only local metadata. No raw URLs or request data."""
    root=private_dir(path.parent)
    raw=json.dumps(report,ensure_ascii=False,separators=(',',':')).encode()
    if not 0<len(raw)<=65536:raise GuardError('Observation receipt size limit')
    fd,name=tempfile.mkstemp(prefix='.ui-review-',dir=root)
    tmp=type(path)(name)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if replace:os.replace(tmp,path)
        else:os.link(tmp,path)
        dfd=os.open(root,os.O_RDONLY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:tmp.unlink(missing_ok=True)


def build_report(snapshot,counts,count,*,confirmed,stage):
    return {'state':stage,'owner_account_attested':confirmed,'account_identity_independently_verified':False,
            **(snapshot or {'exact_card_path_observed':False,'card_id_visible':False,'visible_controls':[]}),
            'request_classes':[{'origin':host,'method':method,'resource_type':kind,'query_present':query,'count':n}
            for (host,method,kind,query),n in sorted(counts.items())],
            'metadata_truncated':count>=MAX_RECORDS,'automatic_route_approval':False,'external_submission_allowed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card',required=True)
    args=parser.parse_args()
    if sys.platform!='darwin' or not sys.stdin.isatty() or not sys.stdout.isatty():parser.error('Interactive local Mac mini terminal required')
    manifest_for(args.card)
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
    try:
        root=private_dir(canonical_root())
        if not (root/'password-profile'/'.tender-agent-b2b-eds-profile').is_file():raise GuardError('Existing dedicated profile required')
        profile=dedicated_profile(root/'password-profile')
        path=root/'manual-ui-observation.json';progress=root/'manual-ui-progress.json'
        if path.exists() or path.is_symlink():raise GuardError('Completed observation already exists')
        with single_runner(root),sync_playwright() as driver:
            counts=Counter();count=[0];snapshot=None
            write_receipt(progress,build_report(None,counts,0,confirmed=False,stage='WAITING_FOR_CARD'),replace=True)
            ctx=driver.chromium.launch_persistent_context(str(profile),channel='chrome',headless=False,timeout=8000,ignore_https_errors=False,chromium_sandbox=True)
            try:
                def note(request):
                    if count[0]>=MAX_RECORDS:return
                    count[0]+=1
                    row=request_metadata(request.url,request.method,request.resource_type)
                    counts[(row['origin'],row['method'],row['resource_type'],row['query_present'])]+=1
                ctx.on('request',note)
                ctx.new_page()
                print('Откройте вручную указанную карточку в выделенном браузере; проверьте кабинет ООО «Арвектум». Не подавайте заявку и не подписывайте документы.')
                print(args.card)
                print('После проверки введите ARVECTUM. Параметры, добавленные площадкой к адресу карточки, не сохраняются.')
                import select
                deadline=time.monotonic()+300;next_check=0
                while time.monotonic()<deadline:
                    if time.monotonic()>=next_check:
                        candidates=[p for p in ctx.pages if manual_card_match(args.card,p.url)]
                        if len(candidates)==1:
                            try:
                                observed=manual_observe(candidates[0],args.card)
                            except (GuardError,PlaywrightError):observed=None
                            if observed is not None:
                                snapshot=observed
                                write_receipt(progress,build_report(snapshot,counts,count[0],confirmed=False,stage='CARD_OBSERVED'),replace=True)
                        next_check=time.monotonic()+2
                    if select.select([sys.stdin],[],[],0)[0]:
                        if sys.stdin.readline().strip()!='ARVECTUM':raise GuardError('Manual confirmation missing')
                        candidates=[p for p in ctx.pages if manual_card_match(args.card,p.url)]
                        if len(candidates)!=1:raise GuardError('Exactly one reviewed card tab required')
                        snapshot=manual_observe(candidates[0],args.card)
                        report=build_report(snapshot,counts,count[0],confirmed=True,stage='MANUAL_UI_REVIEW')
                        write_receipt(path,report)
                        write_receipt(progress,report,replace=True)
                        print(json.dumps({'state':report['state'],'observed_request_classes':len(report['request_classes']),'visible_controls':report['visible_controls']},ensure_ascii=False))
                        return 0
                    live=[p for p in ctx.pages if not p.is_closed()]
                    if not live:raise GuardError('Dedicated browser closed')
                    live[0].wait_for_timeout(250)
                raise GuardError('Manual observation deadline exceeded')
            except Exception as exc:
                report=build_report(snapshot,counts,count[0],confirmed=False,stage='MANUAL_REVIEW_INCOMPLETE')
                report['failure_type']=type(exc).__name__
                write_receipt(progress,report,replace=True)
                raise
            finally:ctx.close()
    except Exception as exc:  # noqa: BLE001 -- never print browser error contents
        print('Manual observation refused: '+type(exc).__name__);return 1


if __name__=='__main__':raise SystemExit(main())
