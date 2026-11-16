"""Bounded inventory of static references from the exact reviewed card HTML.

No script execution, endpoint inference, credential output or automatic expansion
of the live request scope. Only same-origin canonical static paths are candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx
from lxml import html
from lxml.etree import LxmlError

from scripts.research.b2b_guarded_runner import (
    canonical_root,
    private_dir,
    single_runner,
    supervise,
)
from scripts.research.b2b_network_guard import EgressGate, GuardError
from scripts.research.b2b_one_card import manifest_for
from scripts.research.b2b_pilot_preflight import CONSENT, ORIGIN, preflight
from scripts.research.b2b_readonly_broker import ReadOnlyBroker
from scripts.research.b2b_session_policy import ExactScope, cookie_jar, private_json
from src.modules.saas_foundation.commercial_attachment_inventory import (
    attachment_inventory,
)
from src.modules.saas_foundation.commercial_card_evidence import (
    MOSCOW,
    RECEIVING,
    TERMINAL,
    verify_card_snapshot,
)

MAX_HTML=2*1024*1024
STATIC=re.compile(r'/[A-Za-z0-9_./-]{1,240}\.(?:m?js|css)\Z',re.IGNORECASE)


def inventory(card,raw):
    if not 0<len(raw)<=MAX_HTML:raise GuardError('Invalid bounded HTML')
    tree=html.fromstring(raw.decode("utf-8",errors="strict"),parser=html.HTMLParser(no_network=True))
    refs=[];omitted=0;seen=set();foreign_hosts={};reasons={"foreign":0,"query_or_fragment":0,"unsupported_path":0}
    for node in tree.xpath('//script[@src]|//link[@href]')[:200]:
        rel=(node.get('rel') or '').lower().split()
        if node.tag=='link' and not ('stylesheet' in rel or 'modulepreload' in rel or ('preload' in rel and node.get('as') in ('script','style'))):continue
        src=node.get('src') if node.tag=='script' else node.get('href')
        try:
            url=urljoin(card,src);p=urlsplit(url)
            if (p.scheme,p.netloc)!=('https','www.b2b-center.ru'):
                reasons['foreign']+=1;omitted+=1
                host=p.hostname or ''
                if re.fullmatch(r'[A-Za-z0-9.-]{1,253}',host):foreign_hosts[host]=foreign_hosts.get(host,0)+1
                continue
            if p.query or p.fragment:
                reasons['query_or_fragment']+=1;omitted+=1;continue
            if p.username or p.password or not STATIC.fullmatch(p.path) or any(x in ('.','..','') for x in p.path[1:].split('/')) or str(httpx.URL(url))!=url:raise ValueError
        except (ValueError,TypeError,httpx.InvalidURL):omitted+=1;reasons["unsupported_path"]+=1;continue
        if url not in seen:refs.append(url);seen.add(url)
    for node in tree.xpath('//script|//style|//noscript|//svg|//template|//*[@hidden or @aria-hidden="true"]'):
        if node.getparent() is not None:node.drop_tree()
    text=' '.join(tree.text_content().casefold().replace('ё','е').split())
    identifier=manifest_for(card)['card'].rsplit('tender-',1)[1][:-1]
    # Structural metadata only: never return page text, cookie names or account fields.
    headings=[' '.join(n.text_content().split()) for n in tree.xpath('//h1')]
    visible=[' '.join(v.split()) for v in tree.xpath('//body//text()') if v.strip()]
    id_nodes=[v for v in visible if re.fullmatch(r'(?:№\s*|N\s*|Номер(?: закупки)?:?\s*)?'+identifier,v,re.IGNORECASE)]
    structure={'heading_count':len(headings),'standalone_exact_id_count':len(id_nodes),'known_stage_count':sum(v.casefold().replace('ё','е') in ('прием заявок','идет прием заявок','завершен','завершено','прием заявок завершен','отменен','отменено','закрыт') for v in visible[:120]),'known_deadline_count':sum(bool(re.fullmatch(r'до \d{2}\.\d{2}\.20\d{2} \d{2}:\d{2}, по МСК',v)) for v in visible[:150]),'canonical_count':len(tree.xpath('//link[@rel="canonical"]/@href | //meta[@property="og:url"]/@content')),'exact_canonical_count':sum(v==card for v in tree.xpath('//link[@rel="canonical"]/@href | //meta[@property="og:url"]/@content'))}
    return {'html_sha256':hashlib.sha256(raw).hexdigest(),'html_bytes':len(raw),'static_candidates':refs,'omitted_references':omitted,'omission_reasons':reasons,'foreign_host_counts':foreign_hosts,'card_id_in_visible_text':bool(re.search(r'(?<!\d)'+identifier+r'(?!\d)',text)),'challenge_indicator':any(x in text for x in ('captcha','подтвердите, что вы не робот','проверка браузера','access denied')),'login_indicator':any(x in text for x in ('введите пароль','введите логин','вход в личный кабинет')),'visible_text_length':len(text),'structure':structure}


def core_observation(card,response,observed_at):
    """Separate partial observation: never upgrade an incomplete full receipt."""
    if response.status!=200 or response.final_url!=card or observed_at.tzinfo is None or not 0<len(response.data)<=MAX_HTML:raise GuardError('Unverified core transport')
    tree=html.fromstring(response.data.decode('utf-8',errors='strict'),parser=html.HTMLParser(no_network=True))
    declared=tree.xpath('//link[@rel="canonical"]/@href | //meta[@property="og:url"]/@content')
    if not declared or any(u!=card for u in declared):raise GuardError('Exact canonical identity required')
    for node in tree.xpath('//script|//style|//noscript|//svg|//template|//*[@hidden or @aria-hidden="true"]'):
        if node.getparent() is not None:node.drop_tree()
    identifier=manifest_for(card)['card'].rsplit('tender-',1)[1][:-1]
    headings=[' '.join(n.text_content().split()) for n in tree.xpath('//h1')]
    visible=[' '.join(v.split()) for v in tree.xpath('//body//text()') if v.strip()]
    ids=[v for v in visible[:150] if re.fullmatch(r'(?:№\s*|N\s*|Номер(?: закупки)?:?\s*)?'+identifier,v,re.IGNORECASE)]
    if len(headings)!=1 or not 5<len(headings[0])<=500 or len(ids)!=1:raise GuardError('Ambiguous core identity')
    stages=[v for v in visible[:100] if v.casefold().replace('ё','е') in RECEIVING|TERMINAL]
    deadlines=[v for v in visible[:120] if re.fullmatch(r'до \d{2}\.\d{2}\.20\d{2} \d{2}:\d{2}, по МСК',v)]
    if len(stages)!=1 or len(deadlines)!=1:raise GuardError('Ambiguous displayed stage/deadline')
    deadline=datetime.strptime(deadlines[0],'до %d.%m.%Y %H:%M, по МСК').replace(tzinfo=MOSCOW)
    return {'schema':'commercial_b2b_partial_card_observation_v1','external_id':identifier,'source_url':card,'observed_at':observed_at.astimezone(UTC).isoformat(),'html_sha256':hashlib.sha256(response.data).hexdigest(),'title':headings[0],'displayed_stage':stages[0],'displayed_deadline':deadline.isoformat(),'organizer_name_literal':None,'organizer_verified':False,'account_identity_verified':False,'current_live_notice_status_verified':False,'full_documents_verified':False,'external_submission_allowed':False,'human_review_required':True}


def card_evidence(card,response,observed_at):
    result=inventory(card,response.data)
    try:
        receipt=verify_card_snapshot(requested_url=card,final_url=response.final_url,status_code=response.status,tls_verified=True,content_type='text/html',raw=response.data,observed_at=observed_at)
        docs=attachment_inventory(card,response.data)
        result.update(card_observation=receipt,attachment_candidate_count=len(docs['candidates']),opaque_attachment_links=docs['rejected_or_opaque_links'],attachment_coverage_complete=False)
    except (ValueError,LxmlError,UnicodeError) as exc:
        # Only fixed parser field errors, never raw source text or exception values.
        message=str(exc)
        allowed=('heading','stage','deadline','organizer','canonical identity')
        result.update(card_observation=None,card_parser_state='UNSUPPORTED_OBSERVED_LAYOUT',parser_field=next((x for x in allowed if x in message),'other'))
        if result['parser_field']=='organizer':
            try:
                partial=core_observation(card,response,observed_at);docs=attachment_inventory(card,response.data)
                result.update(partial_card_observation=partial,attachment_candidate_count=len(docs['candidates']),opaque_attachment_links=docs['rejected_or_opaque_links'],attachment_coverage_complete=False)
            except (GuardError,ValueError,LxmlError,UnicodeError):pass
    return result


def run(card,root,*,transport=None):
    manifest=manifest_for(card);root=private_dir(root)
    with single_runner(root):
        state=private_json(root/'session.json');preflight(manifest,state);scope=ExactScope(ORIGIN,manifest['routes'])
        gate=EgressGate(private_dir(root/'egress'));broker=ReadOnlyBroker(gate,origin=ORIGIN,permitted=scope,cookies=cookie_jar(state),transport=transport or httpx.HTTPTransport(verify=True,retries=0,trust_env=False,http2=False))
        try:
            r=broker.fetch_one(card);result={'http_status':r.status,'upstream_attempts':1,'account_identity_verified':False}
            if r.status==200 and any(k.lower()=='content-type' and v.lower().startswith('text/html') for k,v in r.headers):result.update(card_evidence(card,r,datetime.now(UTC)))
            return result
        finally:broker.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--card');p.add_argument('--operator-consent');p.add_argument('--confirm-sole-egress',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    try:
        if a.worker:
            cfg=json.loads(sys.stdin.read(4097))
            if set(cfg)!={'card','consent','confirm_sole_egress'} or cfg['consent']!=CONSENT or cfg['confirm_sole_egress'] is not True:raise GuardError('Explicit scope required')
            result=run(cfg['card'],canonical_root())
        else:
            if a.operator_consent!=CONSENT or not a.confirm_sole_egress:raise GuardError('Explicit scope required')
            manifest_for(a.card);result=supervise([sys.executable,'-m','scripts.research.b2b_resource_inventory','--worker'],{'card':a.card,'consent':CONSENT,'confirm_sole_egress':True},seconds=40)
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({'state':'INVENTORY_REFUSED','error_type':type(exc).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
