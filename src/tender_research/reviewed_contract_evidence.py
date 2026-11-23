"""Offline reviewed EIS contract evidence; not a signature verifier.

A trusted reviewer pins exact manifest bytes out of band. Claims point to
exact leaf text in retained XML. No client records enter the company price API.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$', min_length=64,max_length=64)]
Registry = Annotated[str, Field(pattern=r'^[0-9]{19}$',min_length=19,max_length=19)]
MAX_SOURCE = 2 * 1024 * 1024
MAX_MANIFEST = 256 * 1024
SCALE = Decimal('0.000001')


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def sealed(data):
    return digest(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class Anchor(Strict):
    path:list[Annotated[int,Field(ge=0,le=20000)]]=Field(min_length=1,max_length=32)
    tag:str=Field(min_length=1,max_length=512)
    text:str=Field(min_length=1,max_length=8000)


class Contract(Strict):
    registry_number:Registry
    source_sha256:SHA
    source_url:str=Field(min_length=1,max_length=512)
    contract_number:str=Field(min_length=1,max_length=128)
    signed_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    price_rub:str=Field(pattern=r'^[0-9]{1,12}(\.[0-9]{1,2})?$')
    contracted_quantity:str=Field(pattern=r'^[0-9]{1,9}(\.[0-9]{1,4})?$')
    unit:str=Field(min_length=1,max_length=64)
    full_scope:str=Field(min_length=1,max_length=8000)
    tax_terms:str=Field(min_length=1,max_length=1000)
    price_terms:str=Field(min_length=1,max_length=1000)
    signed_status:Anchor
    registry:Anchor
    contract_id:Anchor
    signed_date:Anchor
    currency:Anchor
    price:Anchor
    quantity:Anchor
    quantity_unit:Anchor
    scope:Anchor
    tax:Anchor
    terms:Anchor
    reviewer_confirms_signed_contract:Literal[True]
    reviewer_confirms_exact_quantity_covers_entire_price:Literal[True]
    review_note:str=Field(min_length=20,max_length=2000)

    @model_validator(mode='after')
    def check(self):
        if not re.fullmatch(r'https://zakupki\.gov\.ru/[^\s#]+',self.source_url) or '\\' in self.source_url:
            raise ValueError('Exact official source URL required')
        if Decimal(self.price_rub)<=0 or Decimal(self.contracted_quantity)<=0:
            raise ValueError('Positive signed price and exact contracted quantity required')
        date.fromisoformat(self.signed_on)
        expected={'registry':self.registry_number,'contract_id':self.contract_number,'signed_date':self.signed_on,
                  'currency':'RUB','price':self.price_rub,'quantity':self.contracted_quantity,
                  'quantity_unit':self.unit,'scope':self.full_scope,'tax':self.tax_terms,'terms':self.price_terms}
        for field,wanted in expected.items():
            if getattr(self,field).text!=wanted:raise ValueError('Anchor value mismatch: '+field)
        anchors=[self.signed_status]+[getattr(self,k) for k in expected]
        if len({tuple(a.path) for a in anchors})!=len(anchors):raise ValueError('Distinct evidence fields required')
        return self


class Bundle(Strict):
    schema_version:Literal[1]
    review_id:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    reviewer:str=Field(min_length=1,max_length=128)
    reviewed_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    records:list[Contract]=Field(min_length=1,max_length=20)
    equivalent_registry_numbers:list[Registry]=Field(min_length=1,max_length=20)
    reference_registry_number:Registry
    scope_review_note:str=Field(min_length=20,max_length=2000)
    reviewer_confirms_full_scope_and_price_terms_equivalent:Literal[True]

    @model_validator(mode='after')
    def check(self):
        by_id={r.registry_number:r for r in self.records}
        chosen=self.equivalent_registry_numbers
        if len(by_id)!=len(self.records) or len({r.contract_number for r in self.records})!=len(self.records) or len({r.source_sha256 for r in self.records})!=len(self.records):
            raise ValueError('Duplicate procedure, contract or original')
        if len(set(chosen))!=len(chosen) or self.reference_registry_number not in chosen or not set(chosen)<=set(by_id):
            raise ValueError('Explicit distinct reviewed reference group required')
        reviewed=date.fromisoformat(self.reviewed_on)
        if any(date.fromisoformat(r.signed_on)>reviewed for r in self.records):raise ValueError('Contract after review date')
        ref=by_id[self.reference_registry_number]
        for key in chosen:
            row=by_id[key]
            if (row.full_scope,row.unit,row.tax_terms,row.price_terms)!=(ref.full_scope,ref.unit,ref.tax_terms,ref.price_terms):
                raise ValueError('Exact reviewed scope, unit and price terms must match')
        return self


def parse_original(raw:bytes)->ET.Element:
    if not 0<len(raw)<=MAX_SOURCE:raise ValueError('Original XML size outside bounds')
    # UTF-8 only, no DTD, external entities or processing instructions.
    text=raw.decode('utf-8-sig',errors='strict')
    if '<!' in text or '<?' in re.sub(r'^<\?xml[^?]*\?>','',text,count=1):
        raise ValueError('Unsupported XML declaration or DTD')
    root=ET.fromstring(text)
    count=0
    stack=[(root,0)]
    while stack:
        node,depth=stack.pop();count+=1
        if count>20000 or depth>32:raise ValueError('Original XML structure outside bounds')
        stack.extend((child,depth+1) for child in node)
    return root


def verify_anchor(root:ET.Element,anchor:Anchor):
    node=root
    for index in anchor.path:
        if index>=len(node):raise ValueError('Original anchor path missing')
        node=node[index]
    if len(node) or node.tag!=anchor.tag or node.text!=anchor.text:
        raise ValueError('Original anchor text or tag mismatch')


def _unique_object(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('Duplicate JSON field')
        out[k]=v
    return out


def load_manifest(manifest:bytes,expected_manifest_sha256:str)->Bundle:
    if not 0<len(manifest)<=MAX_MANIFEST or digest(manifest)!=expected_manifest_sha256:
        raise ValueError('Reviewed manifest pin mismatch')
    return Bundle.model_validate(json.loads(manifest.decode('utf-8'),object_pairs_hook=_unique_object))


def intake(manifest:bytes,*,expected_manifest_sha256:str,originals:dict[str,bytes]):
    bundle=load_manifest(manifest,expected_manifest_sha256)
    if set(originals)!={r.source_sha256 for r in bundle.records}:
        raise ValueError('Missing or unexpected original')
    by_id={}
    for r in bundle.records:
        raw=originals[r.source_sha256]
        if not 0<len(raw)<=MAX_SOURCE or digest(raw)!=r.source_sha256:
            raise ValueError('Original size or SHA-256 mismatch')
        root=parse_original(raw)
        for name in ('signed_status','registry','contract_id','signed_date','currency','price','quantity','quantity_unit','scope','tax','terms'):
            verify_anchor(root,getattr(r,name))
        by_id[r.registry_number]=r
    observations=[]
    rates=[]
    with localcontext() as ctx:
        ctx.prec=50
        for key in bundle.equivalent_registry_numbers:
            row=by_id[key]
            rate=Decimal(row.price_rub)/Decimal(row.contracted_quantity)
            rates.append(rate)
            observations.append({'registry_number':key,'contract_number':row.contract_number,
                                 'signed_on':row.signed_on,'signed_contract_price_rub':row.price_rub,
                                 'contracted_exact_full_scope_quantity':row.contracted_quantity,
                                 'unit':row.unit,'source_sha256':row.source_sha256,
                                 'source_url':row.source_url,'unit_price_rub':format(rate.quantize(SCALE,rounding=ROUND_HALF_UP),'f')})
        rates.sort()
        n=len(rates)
        def f(x):
            return format(x.quantize(SCALE,rounding=ROUND_HALF_UP),'f')
        interval={'minimum':f(rates[0]),'median':f((rates[(n-1)//2]+rates[n//2])/2),'maximum':f(rates[-1]),'distinct_procurements':n} if n>=2 else None
    result={'schema':'reviewed_contract_scope_normalization_v1','review_id':bundle.review_id,
            'reviewed_manifest_sha256':expected_manifest_sha256,'reference_registry_number':bundle.reference_registry_number,
            'basis':'REVIEWER_ATTESTED_SIGNED_CONTRACT_PRICE_PER_EXACT_CONTRACTED_FULL_SCOPE_UNIT',
            'currency':'RUB','observations':observations,'range_rub_per_unit':interval,
            'scope_review_note':bundle.scope_review_note,'independent_signature_verification':False,
            'source_authenticity_independently_verified':False,'contract_execution_verified':False,
            'completed_work_quantity_verified':False,'current_market_price':None,'recommendation':None,
            'external_submission_allowed':False,'inputs_stored':False}
    return {**result,'receipt_sha256':sealed(result)}
