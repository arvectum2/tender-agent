"""Private in-memory review bundle, not a submission archive.
Caller must already authorize customer, templates and plan.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select

from src.modules.company_profile_store.models import (
    CompanyDocument,
    CompanyDocumentVersion,
)
from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.document_store.models import ArtifactVersion
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
    calculate_explicit_cost_thresholds,
)

from .source_bound_fill import (
    ReviewedTemplateMap,
    _resolve,
    _utc,
    render_reviewed_identity_draft,
)

_CODE=r'^[a-z][a-z0-9_-]{0,63}$'
Kind=Literal['registry','sme','tax','license','certificate','sro','experience','authority','rights']


class ReviewItem(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code: str=Field(pattern=_CODE)
    role: Literal['FORM','DOCUMENT','ALTERNATIVES','DECLARATION','PRICE','CROSS_REFERENCE']
    applicability: Literal['REQUIRED','CONDITIONAL_UNKNOWN','OPTIONAL_EVIDENCE','NOT_TRIGGERED']
    review_ref: str=Field(min_length=1,max_length=200)
    claims: dict[str,Kind]=Field(default_factory=dict,max_length=8)


class ReviewPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    procurement_ref: str=Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    plan_review_ref: str=Field(min_length=1,max_length=200)
    owner_reviewed_plan: StrictBool
    items: list[ReviewItem]=Field(min_length=1,max_length=64)


def _json(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read_selected(session,root,cid,claim):
    doc=session.scalar(select(CompanyDocument).where(CompanyDocument.customer_id==cid,
        CompanyDocument.document_key==claim['document_key']))
    if not doc:
        raise ValueError('Selected document disappeared')
    version=session.scalar(select(CompanyDocumentVersion).where(CompanyDocumentVersion.company_document_id==doc.id)
        .order_by(CompanyDocumentVersion.version_no.desc()).limit(1))
    if not version or version.version_no!=claim['document_version']:
        raise ValueError('Selected document version changed')
    av=session.scalar(select(ArtifactVersion).where(ArtifactVersion.artifact_ref==doc.artifact_ref,
        ArtifactVersion.version_no==version.artifact_version_no))
    if not av or av.checksum_sha256!=claim['document_sha256']:
        raise ValueError('Selected artifact changed')
    base=root.resolve()/'company-onboarding'/cid
    p=Path(av.storage_uri)
    if base.is_symlink() or base.parent.is_symlink() or p.is_symlink() or p.parent.resolve()!=base.resolve() or p.suffix.lower()!='.pdf':
        raise ValueError('Selected document outside tenant store')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError('Selected document not a regular file')
        data=f.read(10*1024*1024+1)
    if len(data)>10*1024*1024 or not data.startswith(b'%PDF-') or _sha(data)!=claim['document_sha256']:
        raise ValueError('Selected document bytes changed')
    return data


def build_private_review_bundle(session,*,customer_id,root:Path,plan:ReviewPlan,templates:dict[str,tuple[bytes,ReviewedTemplateMap]],
                                selections:dict[str,str],cost:ExplicitCostScenarioRequest|None=None,now=None):
    now=_utc(now or datetime.now(UTC))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',customer_id) or not plan.owner_reviewed_plan or not plan.plan_review_ref.strip():
        raise ValueError('Authorized reviewed plan required')
    items={x.code:x for x in plan.items}
    if len(items)!=len(plan.items) or any(not x.review_ref.strip() for x in items.values()):
        raise ValueError('Duplicate or unreviewed item')
    active={k:v for k,v in items.items() if v.applicability!='NOT_TRIGGERED'}
    if set(templates)-{k for k,x in active.items() if x.role=='FORM'} or set(selections)-{k for k,x in active.items() if x.role in ('DOCUMENT','ALTERNATIVES')}:
        raise ValueError('Unexpected template or attachment selection')
    claims={}
    for x in active.values():
        if x.role=='DOCUMENT' and len(x.claims)!=1 or x.role=='ALTERNATIVES' and len(x.claims)<2 or x.role not in ('DOCUMENT','ALTERNATIVES') and x.claims:
            raise ValueError('Invalid reviewed claim alternatives')
        for code,kind in x.claims.items():
            if code in claims and claims[code]!=kind:
                raise ValueError('Conflicting claim kind')
            claims[code]=kind
    profile=review_profile(session,customer_id=customer_id,root=root,requirements=claims,now=now)
    facts={r['requirement_code']:r for r in profile['requirements']}
    files={}
    inventory=[]
    rows=[]
    total=0
    def add(path,data,role,code):
        nonlocal total
        total+=len(data)
        if path in files or total>64*1024*1024:
            raise ValueError('Bundle limit or duplicate member')
        files[path]=data
        inventory.append({'path':path,'bytes':len(data),'sha256':_sha(data),'role':role,'item_code':code})
    price_items=[x for x in active.values() if x.role=='PRICE']
    if len(price_items)>1 or cost is not None and not price_items:
        raise ValueError('Unexpected price scenario')
    for code,item in items.items():
        row={'code':code,'role':item.role,'applicability':item.applicability,'review_ref':item.review_ref,
             'state':'MISSING_OR_REVIEW_REQUIRED','satisfied':None,'paths':[]}
        if code not in active:
            row['state']='NOT_TRIGGERED_IN_SCENARIO'
        elif item.role=='FORM' and code in templates:
            raw,mapping=templates[code]
            data,receipt=render_reviewed_identity_draft(session,customer_id=customer_id,template_bytes=raw,template_map=mapping,now=now)
            path=f'forms/{code}.{mapping.format}'
            add(path,data,'DRAFT_FORM',code)
            row.update(state='DRAFT_WITH_UNKNOWN_FIELDS' if receipt['unknown_count'] else 'DRAFT_REVIEW_REQUIRED',
                       paths=[path],field_receipt=receipt)
        elif item.role in ('DOCUMENT','ALTERNATIVES'):
            chosen=selections.get(code)
            row['candidate_states']={k:facts[k]['state'] for k in item.claims}
            if chosen is not None:
                if chosen not in item.claims:
                    raise ValueError('Selection outside reviewed alternatives')
                f=facts[chosen]
                if f['state']!='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' or f['claim_assertion']!='PRESENT':
                    raise ValueError('Selected current documentary candidate unavailable')
                data=_read_selected(session,root,customer_id,f)
                path=f'evidence/{code}.pdf'
                add(path,data,'DOCUMENTARY_CANDIDATE',code)
                row.update(state='CANDIDATE_REVIEW_REQUIRED',paths=[path],selected_claim=chosen,source=f)
        elif item.role=='PRICE' and cost is not None:
            if cost.offer_scenario is None:
                raise ValueError('Explicit offer scenario required')
            calc=calculate_explicit_cost_thresholds(cost)
            path='internal/price-scenario.json'
            add(path,_json({'status':'HYPOTHETICAL_PRICE_NOT_OFFER','calculation':calc}),'INTERNAL_SCENARIO',code)
            row.update(state='PRICE_SCENARIO_REVIEW_REQUIRED',paths=[path])
        rows.append(row)
    # The same identity field must agree across all generated forms and
    # match the final current fact projection in this session.
    seen_fields={}
    for row in rows:
        receipt=row.get('field_receipt')
        if receipt:
            current=_resolve(session,customer_id,templates[row['code']][1].fields,now)
            if current!=receipt['fields']:
                raise ValueError('Identity facts changed during bundle assembly')
            for field in current:
                key=field['field_code']
                value=(field['state'],field['value'],field['source'])
                if key in seen_fields and seen_fields[key]!=value:
                    raise ValueError('Identity fields disagree across forms')
                seen_fields[key]=value
    if review_profile(session,customer_id=customer_id,root=root,requirements=claims,now=now)!=profile:
        raise ValueError('Documentary state changed during assembly')
    manifest={'schema':'private-bid-review-v1','status':'DRAFT_REVIEW_ONLY','customer_id':customer_id,
              'procurement_ref':plan.procurement_ref,'plan_review_ref':plan.plan_review_ref,
              'items':rows,'inventory':inventory,'whole_requirements_complete':False,
              'application_ready':False,'go_eligible':False,'signed':False,'submitted':False,'external_delivery':False}
    manifest['unresolved_item_codes']=[r['code'] for r in rows if r['state']!='NOT_TRIGGERED_IN_SCENARIO']
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path,data in sorted(files.items()):
            z.writestr(path,data)
        z.writestr('manifest.json',_json(manifest))
    raw=stream.getvalue()
    verify_private_review_bundle(raw)
    return raw,manifest


def verify_private_review_bundle(raw,*,expected_sha256=None):
    """Internal integrity only, not authenticity or authorization."""
    if expected_sha256 is not None and _sha(raw)!=expected_sha256:
        raise ValueError('Archive differs from pinned external digest')
    if len(raw)>70*1024*1024:
        raise ValueError('Archive too large')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[x.filename for x in infos]
        if len(names)>65 or len(names)!=len(set(names)) or sum(x.file_size for x in infos)>70*1024*1024:
            raise ValueError('Invalid bounded archive')
        m=json.loads(z.read('manifest.json'))
        expected={r['path']:r for r in m['inventory']}
        if (len(expected)!=len(m['inventory']) or set(names)!={'manifest.json',*expected}
                or m['schema']!='private-bid-review-v1' or m['status']!='DRAFT_REVIEW_ONLY'
                or any(m.get(k) is not False for k in ('whole_requirements_complete','application_ready','go_eligible','signed','submitted','external_delivery'))):
            raise ValueError('Archive inventory mismatch')
        rows={r['code']:r for r in m['items']}
        if len(rows)!=len(m['items']) or any(r['satisfied'] is not None for r in rows.values()):
            raise ValueError('Invalid review rows')
        if sorted(m['unresolved_item_codes'])!=sorted(k for k,r in rows.items() if r['state']!='NOT_TRIGGERED_IN_SCENARIO'):
            raise ValueError('Gap report mismatch')
        paths=[p for r in rows.values() for p in r['paths']]
        if len(paths)!=len(set(paths)) or set(paths)!=set(expected):
            raise ValueError('Review row inventory mismatch')
        for path,r in expected.items():
            if not re.fullmatch(r'(?:forms/[a-z][a-z0-9_-]{0,63}\.(?:docx|xlsx)|evidence/[a-z][a-z0-9_-]{0,63}\.pdf|internal/price-scenario\.json)',path):
                raise ValueError('Invalid archive member')
            if r['item_code'] not in rows or path not in rows[r['item_code']]['paths']:
                raise ValueError('Inventory association mismatch')
            data=z.read(path)
            if len(data)!=r['bytes'] or _sha(data)!=r['sha256']:
                raise ValueError('Archive member checksum mismatch')
    return m
