"""Unsigned review drafts. Caller authorizes tenant and reviewed source wording."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from docx import Document
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from sqlalchemy import select

from src.modules.company_profile_store.service import list_current_company_profile_facts
from src.modules.customer_registry.models import CustomerProfile
from src.shared.errors import NotFoundError

from .source_bound_fill import _utc

_MONEY=r'^[0-9]{1,12}(?:\.[0-9]{1,2})?$'
_CODE=r'^[a-z][a-z0-9_-]{0,47}$'
_REF=r'^[A-Za-z0-9_-]{1,64}$'


class OfferLine(BaseModel):
    model_config=ConfigDict(extra='forbid')
    description: str=Field(min_length=1,max_length=300)
    quantity: str=Field(pattern=r'^[0-9]{1,8}(?:\.[0-9]{1,3})?$')
    unit: str=Field(min_length=1,max_length=24)
    gross_unit_price_rub: str=Field(pattern=_MONEY)


class OfferTerms(BaseModel):
    model_config=ConfigDict(extra='forbid')
    procurement_ref: str=Field(pattern=_REF)
    lot_ref: str=Field(pattern=_REF)
    reviewed_source_ref: str=Field(min_length=1,max_length=160)
    lines: list[OfferLine]=Field(min_length=1,max_length=64)
    total_rub: str=Field(pattern=_MONEY)
    ceiling_rub: str=Field(pattern=_MONEY)
    vat_mode: Literal['VAT_EXPLICIT','WITHOUT_VAT_EXPLICIT']
    vat_amount_rub: str=Field(pattern=_MONEY)
    vat_rate_percent: str | None=Field(default=None,pattern=r'^[0-9]{1,2}(?:\.[0-9]{1,2})?$')
    vat_basis: str=Field(min_length=1,max_length=160)
    valid_through: date


class Statement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    code: str=Field(pattern=_CODE)
    exact_wording: str=Field(min_length=1,max_length=1500)
    reviewed_source_ref: str=Field(min_length=1,max_length=160)


class DeclarationTerms(BaseModel):
    model_config=ConfigDict(extra='forbid')
    procurement_ref: str=Field(pattern=_REF)
    statements: list[Statement]=Field(min_length=1,max_length=32)


class ReviewedAssertion(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['commercial-draft-assertion-v1']
    inn: str=Field(pattern=r'^[0-9]{10}$')
    procurement_ref: str=Field(pattern=_REF)
    subject_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    observed_on: date
    owner_confirmed: StrictBool
    assertion: Literal['CONFIRMED','NOT_CONFIRMED']


def subject_digest(model):
    return hashlib.sha256(json.dumps(model.model_dump(mode='json'),ensure_ascii=False,
                                      sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _money(v):
    return Decimal(v).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)


def _text(s):
    if not s.strip() or s!=s.strip() or any(ord(c)<32 or ord(c)==127 for c in s):
        raise ValueError('Invalid reviewed text')
    return s


def _assertion(session,customer_id,procurement,key,digest,now):
    customer=session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==customer_id))
    if customer is None:
        raise NotFoundError('Customer not found')
    facts={f.fact_key:f for f in list_current_company_profile_facts(session,customer_id=customer_id)}
    f=facts.get(key)
    if not f or f.fact_group!='OTHER' or f.source_type!='OWNER_CONFIRMED' or not f.source_ref.strip() or not f.expires_at or _utc(f.expires_at)<=now or _utc(f.created_at)>now:
        return None
    try:
        c=ReviewedAssertion.model_validate(f.value_json)
    except ValidationError:
        return None
    if not (c.owner_confirmed and c.assertion=='CONFIRMED' and c.inn==customer.inn and c.procurement_ref==procurement
            and c.subject_sha256==digest and 0<=(now.date()-c.observed_on).days<=30):
        return None
    return {'fact_id':f.id,'version':f.version_no,'fact_key':key,'source_ref':f.source_ref,
            'observed_on':c.observed_on.isoformat(),'subject_sha256':digest,'customer_id':customer_id}


def _draft(title,procurement):
    d=Document()
    d.add_heading('ПРОЕКТ — НЕ ПОДПИСАНО',0)
    d.add_heading(title,1)
    d.add_paragraph('Закупка: '+procurement)
    return d


def _bytes(d):
    out=io.BytesIO();d.save(out)
    return out.getvalue()


def render_offer(session,*,customer_id,terms,cost,now):
    now=_utc(now)
    _text(terms.reviewed_source_ref);_text(terms.vat_basis)
    if terms.valid_through<now.date():
        raise ValueError('Expired proposed terms')
    total=Decimal(terms.total_rub)
    lines=[]
    for line in terms.lines:
        qty=Decimal(line.quantity);unit=Decimal(line.gross_unit_price_rub)
        if qty<=0 or unit<=0:
            raise ValueError('Nonpositive quantity or price')
        lines.append((_text(line.description),line.quantity,_text(line.unit),format(_money(unit),'f'),format(_money(qty*unit),'f')))
    if total<=0 or sum(Decimal(r[-1]) for r in lines)!=total or total>Decimal(terms.ceiling_rub):
        raise ValueError('Line totals or reviewed ceiling mismatch')
    if not cost or not cost.offer_scenario or Decimal(cost.offer_scenario.offer_price_rub)!=total:
        raise ValueError('Offer differs from PRICE01 scenario')
    vat=Decimal(terms.vat_amount_rub)
    if terms.vat_mode=='WITHOUT_VAT_EXPLICIT':
        if vat or terms.vat_rate_percent is not None:
            raise ValueError('VAT treatment mismatch')
    else:
        rate=Decimal(terms.vat_rate_percent) if terms.vat_rate_percent is not None else None
        if rate is None or vat!=_money(total*rate/(100+rate)):
            raise ValueError('VAT amount/rate mismatch')
    digest=subject_digest(terms)
    source=_assertion(session,customer_id,terms.procurement_ref,'draft_offer:'+terms.procurement_ref,digest,now)
    receipt={'status':'OFFER_OWNER_REVIEW_REQUIRED' if source else 'OFFER_CONFIRMATION_MISSING',
             'subject_sha256':digest,'source':source,'vat_legal_basis_verified':False,
             'vat_effect_on_economics_verified':False,'application_ready':False,'signed':False,'submitted':False}
    if not source:
        return None,receipt
    d=_draft('Проект ценового предложения',terms.procurement_ref)
    d.add_paragraph('Лот: '+terms.lot_ref)
    table=d.add_table(rows=1,cols=5);table.style='Table Grid'
    for c,t in zip(table.rows[0].cells,('Наименование','Количество','Ед.','Цена за ед., руб.','Сумма, руб.'),strict=True):c.text=t
    for line in lines:
        for c,t in zip(table.add_row().cells,line,strict=True):c.text=t
    d.add_paragraph('Итого: '+format(_money(total),'f')+' руб.')
    d.add_paragraph(('НДС: '+format(_money(vat),'f')+' руб., ставка '+str(terms.vat_rate_percent)+'%' if terms.vat_mode=='VAT_EXPLICIT' else 'Без НДС')+'. Основание: '+terms.vat_basis)
    d.add_paragraph('Срок действия проекта: '+terms.valid_through.isoformat())
    d.add_paragraph('Подпись: __________________')
    return _bytes(d),receipt


def render_declarations(session,*,customer_id,terms,now):
    now=_utc(now)
    if len({s.code for s in terms.statements})!=len(terms.statements):
        raise ValueError('Duplicate declaration code')
    d=_draft('Проект деклараций участника',terms.procurement_ref)
    rows=[]
    for s in terms.statements:
        _text(s.exact_wording);_text(s.reviewed_source_ref)
        digest=subject_digest(DeclarationTerms(procurement_ref=terms.procurement_ref,statements=[s]))
        source=_assertion(session,customer_id,terms.procurement_ref,
                          'draft_declaration:'+s.code,digest,now)
        if source:
            d.add_paragraph(s.exact_wording)
            d.add_paragraph('Ответ проекта: подтверждено владельцем для проверки.')
        else:
            d.add_paragraph('Пункт '+s.code+': требуется подтверждение; заявление не заполнено.')
        rows.append({'code':s.code,'subject_sha256':digest,'source':source,
                     'state':'OWNER_CONFIRMED_REVIEW_REQUIRED' if source else 'UNANSWERED',
                     'semantic_verified':False,'legal_satisfied':None})
    d.add_paragraph('Подпись: __________________')
    return _bytes(d),{'status':'DECLARATIONS_DRAFT_REVIEW_ONLY','rows':rows,
                      'unanswered_count':sum(r['source'] is None for r in rows),
                      'application_ready':False,'signed':False,'submitted':False}
