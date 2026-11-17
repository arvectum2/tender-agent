"""Read-only, code-pinned releases of reviewed historical contract receipts.

Release membership is a repository review decision, never a user upload.
Only latest membership is active. Previous releases remain immutable.
No original XML or private manifest is served.
"""
from __future__ import annotations

import json
import os
import re
import stat
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from src.tender_research.reviewed_contract_evidence import (
    SHA,
    Registry,
    Strict,
    _unique_object,
    digest,
    sealed,
)

ROOT=Path(__file__).resolve().parents[2]/'docs/roadmap/price01_contract_registry'
RELEASE_PINS=('c519913cf71ececa580e3c10d364c042b78176f29dcef5c642480996fb3b8b16',)
MAX_RELEASE=64*1024
MAX_RECEIPT=128*1024
MAX_RELEASES=32
MAX_ENTRIES=20
SCALE=Decimal('0.000001')
BASIS='REVIEWER_ATTESTED_SIGNED_CONTRACT_PRICE_PER_EXACT_CONTRACTED_FULL_SCOPE_UNIT'


class Entry(Strict):
    review_id:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    reviewed_manifest_sha256:SHA
    receipt_file_sha256:SHA
    receipt_sha256:SHA
    public_scope_label:str=Field(min_length=1,max_length=160)


class Release(Strict):
    schema_name: Literal['reviewed_contract_registry_release_v1']=Field(alias='schema')
    version:int=Field(ge=1,le=MAX_RELEASES)
    previous_release_sha256:SHA|None
    published_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    entries:list[Entry]=Field(max_length=MAX_ENTRIES)

    @model_validator(mode='after')
    def validate_release(self):
        date.fromisoformat(self.published_on)
        for field in ('review_id','reviewed_manifest_sha256','receipt_file_sha256','receipt_sha256'):
            if len({getattr(e,field) for e in self.entries})!=len(self.entries):
                raise ValueError('Duplicate release entry')
        return self


class Observation(Strict):
    registry_number:Registry
    contract_number:str=Field(min_length=1,max_length=128)
    signed_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    signed_contract_price_rub:str=Field(pattern=r'^[0-9]{1,12}(\.[0-9]{1,2})?$')
    contracted_exact_full_scope_quantity:str=Field(pattern=r'^[0-9]{1,9}(\.[0-9]{1,4})?$')
    unit:str=Field(min_length=1,max_length=64)
    source_sha256:SHA
    source_url:str=Field(min_length=1,max_length=512)
    unit_price_rub:str=Field(pattern=r'^[0-9]{1,16}\.[0-9]{6}$')

    @model_validator(mode='after')
    def validate_source(self):
        date.fromisoformat(self.signed_on)
        if not re.fullmatch(r'https://zakupki\.gov\.ru/[^\s#]+',self.source_url) or '\\' in self.source_url:
            raise ValueError('Invalid source origin')
        if Decimal(self.signed_contract_price_rub)<=0 or Decimal(self.contracted_exact_full_scope_quantity)<=0:
            raise ValueError('Positive exact source values required')
        return self


class PriceRange(Strict):
    minimum:str
    median:str
    maximum:str
    distinct_procurements:int=Field(ge=2,le=20)


class Receipt(Strict):
    schema_name:Literal['reviewed_contract_scope_normalization_v1']=Field(alias='schema')
    review_id:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    reviewed_manifest_sha256:SHA
    reference_registry_number:Registry
    basis:Literal['REVIEWER_ATTESTED_SIGNED_CONTRACT_PRICE_PER_EXACT_CONTRACTED_FULL_SCOPE_UNIT']
    currency:Literal['RUB']
    observations:list[Observation]=Field(min_length=1,max_length=20)
    range_rub_per_unit:PriceRange|None
    scope_review_note:str=Field(min_length=20,max_length=2000)
    independent_signature_verification:Literal[False]
    source_authenticity_independently_verified:Literal[False]
    contract_execution_verified:Literal[False]
    completed_work_quantity_verified:Literal[False]
    current_market_price:None
    recommendation:None
    external_submission_allowed:Literal[False]
    inputs_stored:Literal[False]
    receipt_sha256:SHA

    @model_validator(mode='after')
    def verify(self):
        rows=self.observations
        for field in ('registry_number','contract_number','source_sha256'):
            if len({getattr(r,field) for r in rows})!=len(rows):
                raise ValueError('Duplicate contract observation')
        if self.reference_registry_number not in {r.registry_number for r in rows} or len({r.unit for r in rows})!=1:
            raise ValueError('Reference and exact unit required')
        with localcontext() as ctx:
            ctx.prec=50
            def fmt(x):
                return format(x.quantize(SCALE,rounding=ROUND_HALF_UP),'f')
            amounts=[]
            for row in rows:
                rate=Decimal(row.signed_contract_price_rub)/Decimal(row.contracted_exact_full_scope_quantity)
                if row.unit_price_rub!=fmt(rate):raise ValueError('Contract unit price mismatch')
                amounts.append(rate)
            amounts.sort();n=len(amounts)
            expected=PriceRange(minimum=fmt(amounts[0]),median=fmt((amounts[(n-1)//2]+amounts[n//2])/2),maximum=fmt(amounts[-1]),distinct_procurements=n) if n>=2 else None
            if self.range_rub_per_unit!=expected:raise ValueError('Contract range mismatch')
        if sealed(self.model_dump(mode='json',by_alias=True,exclude={'receipt_sha256'}))!=self.receipt_sha256:
            raise ValueError('Receipt digest mismatch')
        return self


def read_pinned(path:Path,pin:str,limit:int)->bytes:
    if not re.fullmatch(r'[0-9a-f]{64}',pin):raise ValueError('Invalid trusted pin')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        meta=os.fstat(f.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 0<meta.st_size<=limit:
            raise ValueError('Invalid registry file')
        raw=f.read(limit+1)
    if not 0<len(raw)<=limit or digest(raw)!=pin:
        raise ValueError('Registry pinned bytes mismatch')
    return raw


def parse(raw:bytes,model):
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_object)
    obj=model.model_validate(value)
    # Prevent coercion (e.g. number instead of bool) or dropped fields.
    if sealed(value)!=sealed(obj.model_dump(mode='json',by_alias=True)):
        raise ValueError('Noncanonical registry field types')
    return obj


def load_registry(root:Path=ROOT,pins:tuple[str,...]=RELEASE_PINS):
    """Release pins are supplied by trusted code, never request or environment."""
    if not 1<=len(pins)<=MAX_RELEASES or len(set(pins))!=len(pins):
        raise ValueError('Invalid release pin chain')
    chain=[]
    identities={}
    known_receipts={}
    for i,pin in enumerate(pins,1):
        release=parse(read_pinned(root/'releases'/f'{i:04d}.json',pin,MAX_RELEASE),Release)
        if release.version!=i or release.previous_release_sha256!=(pins[i-2] if i>1 else None):
            raise ValueError('Release chain broken')
        if chain and release.published_on<chain[-1]['published_on']:
            raise ValueError('Release date reversed')
        active=[]
        seen={k:set() for k in ('registry_number','contract_number','source_sha256')}
        for entry in release.entries:
            old=identities.get(entry.review_id)
            if old is not None and old!=entry:raise ValueError('Reviewed identity changed; create new review')
            identities[entry.review_id]=entry
            if len(identities)>64:raise ValueError('Registry historical group limit')
            receipt=known_receipts.get(entry.receipt_file_sha256)
            if receipt is None:
                receipt=parse(read_pinned(root/'receipts'/(entry.receipt_file_sha256+'.json'),entry.receipt_file_sha256,MAX_RECEIPT),Receipt)
                known_receipts[entry.receipt_file_sha256]=receipt
            if (receipt.review_id,receipt.reviewed_manifest_sha256,receipt.receipt_sha256)!=(entry.review_id,entry.reviewed_manifest_sha256,entry.receipt_sha256):
                raise ValueError('Trusted review binding mismatch')
            if any(r.signed_on>release.published_on for r in receipt.observations):
                raise ValueError('Contract after publication')
            for field,values in seen.items():
                next_values={getattr(o,field) for o in receipt.observations}
                if values&next_values:raise ValueError('Overlapping procurement groups')
                values.update(next_values)
            # Deliberately omit URL, review note, original XML/manifest and reviewer.
            rows=[o.model_dump(mode='json',exclude={'source_url'}) for o in receipt.observations]
            active.append({'review_id':entry.review_id,'reviewed_manifest_sha256':entry.reviewed_manifest_sha256,
                           'receipt_sha256':entry.receipt_sha256,'receipt_file_sha256':entry.receipt_file_sha256,
                           'reviewer_scope_label':entry.public_scope_label,'reference_registry_number':receipt.reference_registry_number,
                           'unit':rows[0]['unit'],'basis':BASIS,'currency':'RUB','observations':rows,
                           'range_rub_per_unit':receipt.range_rub_per_unit.model_dump(mode='json') if receipt.range_rub_per_unit else None})
        chain.append({'version':i,'release_sha256':pin,'previous_release_sha256':release.previous_release_sha256,
                      'published_on':release.published_on,'active_groups_count':len(active)})
    return {'release':chain[-1],'release_history':chain,'groups':active,
            'independent_signature_verification':False,'source_authenticity_independently_verified':False,
            'contract_execution_verified':False,'completed_work_quantity_verified':False,
            'current_market_price':None,'recommendation':None,'external_submission_allowed':False,
            'inputs_stored':False}
