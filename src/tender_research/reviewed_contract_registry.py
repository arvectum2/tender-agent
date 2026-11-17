"""Immutable, review-pinned publication ledger. No runtime write route.

Publishing requires a repository change to the exact release bytes and the
compiled pin. Offline candidates do not become trusted simply by hashing them.
"""
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import Field, model_validator

from src.tender_research.reviewed_contract_evidence import (
    SCALE,
    SHA,
    Registry,
    Strict,
    _unique_object,
    digest,
    sealed,
)

MAX_RELEASE=512*1024
MAX_EVENTS=40
GroupID=Annotated[str,Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')]


class Observation(Strict):
    registry_number:Registry
    contract_number:str=Field(min_length=1,max_length=128)
    signed_on:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    signed_contract_price_rub:str=Field(pattern=r'^[0-9]{1,12}(\.[0-9]{1,2})?$')
    contracted_exact_full_scope_quantity:str=Field(pattern=r'^[0-9]{1,9}(\.[0-9]{1,4})?$')
    unit:str=Field(min_length=1,max_length=64)
    source_sha256:SHA
    unit_price_rub:str=Field(pattern=r'^[0-9]{1,16}\.[0-9]{6}$')

    @model_validator(mode='after')
    def check(self):
        from datetime import date
        date.fromisoformat(self.signed_on)
        if Decimal(self.signed_contract_price_rub)<=0 or Decimal(self.contracted_exact_full_scope_quantity)<=0:
            raise ValueError('Positive exact price and quantity required')
        with localcontext() as ctx:
            ctx.prec=50
            actual=Decimal(self.signed_contract_price_rub)/Decimal(self.contracted_exact_full_scope_quantity)
            if format(actual.quantize(SCALE,rounding=ROUND_HALF_UP),'f')!=self.unit_price_rub:
                raise ValueError('Published unit price mismatch')
        return self


class Range(Strict):
    minimum:str
    median:str
    maximum:str
    distinct_procurements:int=Field(ge=2,le=20)


def group_range(rows):
    if len(rows)<2:return None
    with localcontext() as ctx:
        ctx.prec=50
        rates=sorted(Decimal(x.signed_contract_price_rub)/Decimal(x.contracted_exact_full_scope_quantity) for x in rows)
        n=len(rates)
        def f(x):return format(x.quantize(SCALE,rounding=ROUND_HALF_UP),'f')
        return {'minimum':f(rates[0]),'median':f((rates[(n-1)//2]+rates[n//2])/2),'maximum':f(rates[-1]),'distinct_procurements':n}


class Group(Strict):
    group_id:GroupID
    reviewed_manifest_sha256:SHA
    intake_receipt_sha256:SHA
    reference_registry_number:Registry
    full_scope:str=Field(min_length=1,max_length=8000)
    tax_terms:str=Field(min_length=1,max_length=1000)
    price_terms:str=Field(min_length=1,max_length=1000)
    currency:Literal['RUB']
    unit:str=Field(min_length=1,max_length=64)
    observations:list[Observation]=Field(min_length=1,max_length=20)
    range_rub_per_unit:Range|None

    @model_validator(mode='after')
    def check(self):
        rows=self.observations
        for attr in ('registry_number','contract_number','source_sha256'):
            if len({getattr(x,attr) for x in rows})!=len(rows):raise ValueError('Duplicate group source')
        if self.reference_registry_number not in {x.registry_number for x in rows} or any(x.unit!=self.unit for x in rows):
            raise ValueError('Group reference or unit mismatch')
        if (self.range_rub_per_unit.model_dump() if self.range_rub_per_unit else None)!=group_range(rows):
            raise ValueError('Published range mismatch')
        return self


class Event(Strict):
    revision:int=Field(ge=1,le=MAX_EVENTS)
    previous_event_sha256:SHA|None
    action:Literal['PUBLISH','WITHDRAW']
    group_id:GroupID
    group:Group|None
    reason: str=Field(min_length=10,max_length=500)
    event_sha256:SHA

    @model_validator(mode='after')
    def check(self):
        if (self.action=='PUBLISH')!=(self.group is not None) or (self.group and self.group.group_id!=self.group_id):
            raise ValueError('Invalid publication action')
        if sealed(self.model_dump(mode='json',exclude={'event_sha256'}))!=self.event_sha256:
            raise ValueError('Event digest mismatch')
        return self


class Release(Strict):
    schema:Literal['price01_reviewed_contract_registry_v1']
    events:list[Event]=Field(max_length=MAX_EVENTS)


def replay(release:Release):
    active={};seen=set();pins=set();withdrawn=[];prior=None
    for i,event in enumerate(release.events,1):
        if event.revision!=i or event.previous_event_sha256!=prior:raise ValueError('Broken release chain')
        prior=event.event_sha256
        if event.action=='PUBLISH':
            group=event.group
            if group is None or event.group_id in seen or group.reviewed_manifest_sha256 in pins:
                raise ValueError('Reused publication identity')
            for old in active.values():
                for attr in ('registry_number','contract_number','source_sha256'):
                    if {getattr(x,attr) for x in old.observations}&{getattr(x,attr) for x in group.observations}:
                        raise ValueError('Source duplicated across active groups')
            active[event.group_id]=group;seen.add(event.group_id);pins.add(group.reviewed_manifest_sha256)
        else:
            if event.group_id not in active:raise ValueError('Withdrawal requires active group')
            del active[event.group_id];withdrawn.append({'group_id':event.group_id,'revision':event.revision,'reason':event.reason})
    return active,withdrawn


def load_release(raw:bytes,pin:str)->Release:
    if not 0<len(raw)<=MAX_RELEASE or digest(raw)!=pin:raise ValueError('Release pin mismatch')
    release=Release.model_validate(json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_object))
    replay(release)
    return release


def append_candidate(release:Release,*,action,group_id,reason,group=None):
    payload={'revision':len(release.events)+1,
             'previous_event_sha256':release.events[-1].event_sha256 if release.events else None,
             'action':action,'group_id':group_id,'group':group.model_dump(mode='json') if group else None,'reason':reason}
    event=Event.model_validate({**payload,'event_sha256':sealed(payload)})
    candidate=Release.model_validate({'schema':release.schema,'events':[e.model_dump(mode='json') for e in release.events]+[event.model_dump(mode='json')]})
    replay(candidate)
    raw=(json.dumps(candidate.model_dump(mode='json'),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    if len(raw)>MAX_RELEASE:raise ValueError('Release size limit')
    return raw


def publication_group(manifest:bytes,reviewed_pin:str,originals:dict[str,bytes],group_id:str)->Group:
    from src.tender_research.reviewed_contract_evidence import intake, load_manifest
    source=load_manifest(manifest,reviewed_pin)
    receipt=intake(manifest,expected_manifest_sha256=reviewed_pin,originals=originals)
    ref=next(x for x in source.records if x.registry_number==source.reference_registry_number)
    return Group.model_validate({'group_id':group_id,'reviewed_manifest_sha256':reviewed_pin,
        'intake_receipt_sha256':receipt['receipt_sha256'],'reference_registry_number':ref.registry_number,
        'full_scope':ref.full_scope,'tax_terms':ref.tax_terms,'price_terms':ref.price_terms,'unit':ref.unit,'currency':'RUB',
        'observations':[{k:v for k,v in row.items() if k!='source_url'} for row in receipt['observations']],
        'range_rub_per_unit':receipt['range_rub_per_unit']})
