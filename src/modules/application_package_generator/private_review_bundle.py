"""Private draft ZIP only; trusted in-process caller, no upload or DB writes."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.modules.company_profile_store.qualification_readiness import review_profile
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
    calculate_explicit_cost_thresholds,
)

from .source_bound_fill import ReviewedTemplateMap, render_reviewed_identity_draft

_CODE=r'^[a-z][a-z0-9_-]{0,47}$'
_SCOPE=r'^[A-Za-z0-9:_-]{1,96}$'
_LIMIT=32*1024*1024
Kind=Literal['registry','sme','tax','license','certificate','sro','experience','authority','rights']
Applicability=Literal['REQUIRED','CONDITIONAL_UNKNOWN','NOT_TRIGGERED','OPTIONAL_EVIDENCE']


class FormPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code: str=Field(pattern=_CODE)
    source_ref: str=Field(min_length=1,max_length=256)
    template_map: ReviewedTemplateMap | None=None


class AttachmentPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code: str=Field(pattern=_CODE)
    source_ref: str=Field(min_length=1,max_length=256)
    applicability: Applicability
    alternatives: dict[str,Kind]=Field(min_length=1,max_length=8)
    selected_claim: str | None=None

    @model_validator(mode='after')
    def valid_selection(self):
        if any(not re.fullmatch(_CODE,k) for k in self.alternatives):
            raise ValueError('Invalid attachment claim code')
        if self.selected_claim is not None and (self.selected_claim not in self.alternatives or self.applicability in ('NOT_TRIGGERED','CONDITIONAL_UNKNOWN')):
            raise ValueError('Invalid explicit attachment selection')
        return self


class ReviewBundlePlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    customer_id: str=Field(pattern=_SCOPE)
    procurement_ref: str=Field(pattern=_SCOPE)
    plan_review_ref: str=Field(min_length=1,max_length=160)
    owner_reviewed_plan: StrictBool
    forms: list[FormPlan]=Field(min_length=1,max_length=8)
    attachments: list[AttachmentPlan]=Field(max_length=16)
    unresolved_requirement_codes: list[str]=Field(min_length=1,max_length=32)
    price_scenario: ExplicitCostScenarioRequest | None=None

    @model_validator(mode='after')
    def unique_codes(self):
        codes=[x.code for x in self.forms]+[x.code for x in self.attachments]+self.unresolved_requirement_codes
        if len(codes)!=len(set(codes)) or any(not re.fullmatch(_CODE,k) for k in codes) or 'commercial_offer' in codes:
            raise ValueError('Duplicate or invalid requirement code')
        return self


def _json(data):
    return (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_private_review_bundle(session,*,customer_id:str,procurement_ref:str,root:Path,plan:ReviewBundlePlan,
                                templates:dict[str,bytes],now:datetime|None=None):
    """Return private ZIP bytes and integrity receipt, not legal readiness."""
    plan=ReviewBundlePlan.model_validate(plan.model_dump())
    if (not plan.owner_reviewed_plan or not plan.plan_review_ref.strip()
            or customer_id!=plan.customer_id or procurement_ref!=plan.procurement_ref):
        raise ValueError('Plan review and scope must match')
    now=now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Assessment time must be timezone aware')
    now=now.astimezone(UTC)
    if set(templates)-{f.code for f in plan.forms} or any(type(raw) is not bytes for raw in templates.values()):
        raise ValueError('Unexpected template input')
    if sum(map(len,templates.values()))>_LIMIT:
        raise ValueError('Template inputs exceed bundle limit')
    review_profile(session,customer_id=customer_id,root=root,requirements={},now=now)
    files={};inventory=[];gaps=[];receipts={}
    refs={item.code:item.source_ref for item in [*plan.forms,*plan.attachments]}
    def add(name,raw,role,code):
        if name in files or sum(map(len,files.values()))+len(raw)>_LIMIT:
            raise ValueError('Duplicate path or bundle size limit')
        files[name]=raw
        inventory.append({'path':name,'role':role,'requirement_code':code,'source_ref':refs.get(code),
                          'size_bytes':len(raw),'sha256':_sha(raw)})
    def gap(code,reason,**detail):
        gaps.append({'code':code,'source_ref':refs.get(code),'reason':reason,**detail})
    for form in plan.forms:
        if form.template_map is None or form.code not in templates:
            gap(form.code,'REVIEWED_TEMPLATE_OR_MAP_MISSING')
            continue
        output,receipt=render_reviewed_identity_draft(session,customer_id=customer_id,
            template_bytes=templates[form.code],template_map=form.template_map,now=now)
        receipts[form.code]=receipt
        add(f'draft_forms/{form.code}.{form.template_map.format}',output,'UNSIGNED_DRAFT',form.code)
        for field in receipt['fields']:
            if field['value'] is None:
                gap(form.code,field['state'],field_code=field['field_code'],target_locator=field['target_locator'])
        gap(form.code,'FULL_FORM_AND_DECLARATION_REVIEW_REQUIRED')
    for item in plan.attachments:
        if item.applicability=='NOT_TRIGGERED':
            receipts[item.code]={'state':'NOT_TRIGGERED_IN_REVIEWED_PLAN'}
            continue
        if item.applicability=='CONDITIONAL_UNKNOWN':
            gap(item.code,'APPLICABILITY_UNKNOWN')
            continue
        if item.selected_claim is None:
            gap(item.code,'EXPLICIT_CHOICE_REQUIRED',alternatives=list(item.alternatives))
            continue
        code=item.selected_claim
        captured={}
        p=review_profile(session,customer_id=customer_id,root=root,requirements={code:item.alternatives[code]},now=now,_capture=captured)
        row=p['requirements'][0]
        receipts[item.code]=row
        raw=captured.get(code)
        if (row['state']!='DOCUMENTED_OWNER_CLAIM_REVIEW_REQUIRED' or row['claim_assertion']!='PRESENT'
                or raw is None or _sha(raw)!=row['document_sha256']):
            gap(item.code,'CANDIDATE_MISSING_OR_UNCONFIRMED',candidate_state=row['state'])
            continue
        add(f'candidate_attachments/{item.code}.pdf',raw,'DOCUMENTARY_CANDIDATE',item.code)
        gap(item.code,'SEMANTIC_AND_LEGAL_REVIEW_REQUIRED')
    for code in plan.unresolved_requirement_codes:
        gap(code,'REVIEWED_PLAN_OPEN_REQUIREMENT')
    if plan.price_scenario is not None:
        price=calculate_explicit_cost_thresholds(plan.price_scenario)
        add('internal_review/price_scenario.json',_json(price),'INTERNAL_HYPOTHETICAL_ECONOMICS',None)
    gap('commercial_offer','ACTUAL_APPROVED_PRICE_REQUIRED')
    add('internal_review/field_and_document_provenance.json',_json(receipts),'PRIVATE_PROVENANCE',None)
    add('internal_review/gaps.json',_json(gaps),'PRIVATE_GAP_REPORT',None)
    add('README_REVIEW_ONLY.txt',b'PRIVATE REVIEW ONLY. Not a submission or approved offer. Do not upload this archive. Internal economics and provenance are private.\n','PRIVATE_WARNING',None)
    plan_bytes=_json(plan.model_dump(mode='json'))
    add('internal_review/reviewed_plan.json',plan_bytes,'PRIVATE_REVIEWED_PLAN',None)
    manifest={'schema':'private-review-bundle-v1','customer_id':customer_id,'procurement_ref':procurement_ref,
              'plan_review_ref':plan.plan_review_ref,'assessment_at':now.isoformat(),'inventory':inventory,
              'plan_sha256':_sha(plan_bytes),'gap_count':len(gaps),
              'whole_requirements_complete':False,'application_ready':False,'commercial_price_approved':False,
              'signature_performed':False,'submission_performed':False,'external_delivery_performed':False}
    manifest_bytes=_json(manifest)
    if sum(map(len,files.values()))+len(manifest_bytes)>_LIMIT:
        raise ValueError('Manifest exceeds bundle size limit')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):
            z.writestr(name,raw)
        z.writestr('internal_review/inventory.json',manifest_bytes)
    raw=out.getvalue()
    return raw,{'status':'PRIVATE_REVIEW_ONLY','archive_sha256':_sha(raw),'inventory_sha256':_sha(manifest_bytes),
                'file_count':len(files)+1,'gap_count':len(gaps),'application_ready':False,
                'submission_performed':False,'external_delivery_performed':False}


def verify_private_review_bundle(raw:bytes,*,expected_sha256:str,customer_id:str,procurement_ref:str):
    """Integrity only against separately retained digest and explicit scope."""
    if len(raw)>_LIMIT+1024*1024 or _sha(raw)!=expected_sha256:
        raise ValueError('Archive digest or size mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=z.infolist()
        names=[i.filename for i in entries]
        if (len(entries)>40 or len(names)!=len(set(names)) or sum(i.file_size for i in entries)>_LIMIT
                or any(i.flag_bits&1 or i.is_dir() for i in entries)):
            raise ValueError('Invalid bundle envelope')
        name='internal_review/inventory.json'
        if name not in names:
            raise ValueError('Inventory missing')
        m=json.loads(z.read(name))
        if (m.get('schema')!='private-review-bundle-v1' or m.get('customer_id')!=customer_id
                or m.get('procurement_ref')!=procurement_ref):
            raise ValueError('Bundle scope mismatch')
        flags=('whole_requirements_complete','application_ready','commercial_price_approved',
               'signature_performed','submission_performed','external_delivery_performed')
        if any(m.get(f) is not False for f in flags):
            raise ValueError('Unexpected readiness or external action claim')
        listed=m['inventory'];paths=[i['path'] for i in listed]
        if len(paths)!=len(set(paths)) or name in paths or set(paths)!=set(names)-{name}:
            raise ValueError('Inventory members mismatch')
        for row in listed:
            path=row['path']
            if not re.fullmatch(r'(?:draft_forms/[a-z][a-z0-9_-]{0,47}\.(?:docx|xlsx)|candidate_attachments/[a-z][a-z0-9_-]{0,47}\.pdf|internal_review/[a-z_]+\.json|README_REVIEW_ONLY\.txt)',path):
                raise ValueError('Unexpected review archive path')
            data=z.read(path)
            if len(data)!=row['size_bytes'] or _sha(data)!=row['sha256']:
                raise ValueError('Inventory member digest mismatch')
        plan_bytes=z.read('internal_review/reviewed_plan.json')
        plan=ReviewBundlePlan.model_validate_json(plan_bytes)
        if (plan.customer_id!=customer_id or plan.procurement_ref!=procurement_ref or not plan.owner_reviewed_plan
                or plan.plan_review_ref!=m['plan_review_ref'] or _sha(plan_bytes)!=m['plan_sha256']
                or len(json.loads(z.read('internal_review/gaps.json')))!=m['gap_count']):
            raise ValueError('Plan or gap report mismatch')
    return {'status':'INTEGRITY_MATCH_ONLY','archive_sha256':expected_sha256,'file_count':len(names),
            'gap_count':m['gap_count'],'application_ready':False}
