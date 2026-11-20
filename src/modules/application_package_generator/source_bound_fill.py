"""Private draft-only autofill with a reviewed template map and immutable fact provenance.

Caller must already be authorized for the customer and template. No route,
DB mutation, signing, attachment or submission from this module.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import UTC, date, datetime
from typing import Literal

from docx import Document
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from sqlalchemy import select

from src.modules.company_profile_store.service import list_current_company_profile_facts
from src.modules.customer_registry.models import CustomerProfile
from src.shared.errors import NotFoundError

from .service import _iter_docx_paragraphs, _merged_anchor_or_fail, _parse_xlsx_locator

FieldCode=Literal['legal_name','inn','kpp','ogrn','legal_address','postal_address']
_SHA=r'^[0-9a-f]{64}$'


class ReviewedField(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    field_code: FieldCode
    target_locator: str=Field(min_length=1,max_length=160)
    expected_placeholder: str=Field(min_length=1,max_length=160)


class ReviewedTemplateMap(BaseModel):
    model_config=ConfigDict(extra='forbid')
    template_sha256: str=Field(pattern=_SHA)
    format: Literal['docx','xlsx']
    map_review_ref: str=Field(min_length=1,max_length=160)
    owner_reviewed_mapping: StrictBool
    fields: list[ReviewedField]=Field(min_length=1,max_length=64)


class IdentityValue(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal['draft-identity-value-v1']
    inn: str=Field(pattern=r'^\d{10}$')
    field_code: FieldCode
    value: str=Field(min_length=1,max_length=500)
    observed_on: date
    owner_confirmed: StrictBool


def _utc(dt):
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _valid(code,value,customer):
    if value!=value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
        return False
    if value[0] in '=+-@':
        return False
    widths={'inn':10,'kpp':9,'ogrn':13}
    if code in widths and not re.fullmatch(r'[0-9]{'+str(widths[code])+r'}',value):
        return False
    return not (code in ('legal_name', 'inn', 'kpp') and value != getattr(customer, code))


def _resolve(session,customer_id,fields,now):
    customer=session.scalar(select(CustomerProfile).where(CustomerProfile.customer_id==customer_id))
    if customer is None:
        raise NotFoundError('Customer not found')
    facts={r.fact_key:r for r in list_current_company_profile_facts(session,customer_id=customer_id)}
    results=[]
    for field in fields:
        code=field.field_code
        fact=facts.get('draft_identity:'+code)
        row={'field_code':code,'target_locator':field.target_locator,'state':'MISSING','value':None,'source':None}
        if fact is not None:
            row['state']='UNREVIEWED_OR_EXPIRED'
            if (fact.fact_group=='IDENTITY' and fact.source_type=='OWNER_CONFIRMED' and fact.source_ref.strip()
                    and fact.expires_at and _utc(fact.expires_at)>now and _utc(fact.created_at)<=now):
                try:
                    claim=IdentityValue.model_validate(fact.value_json)
                except ValidationError:
                    row['state']='INVALID_SOURCE'
                else:
                    if (claim.owner_confirmed and claim.inn==customer.inn and claim.field_code==code
                            and 0<=(now.date()-claim.observed_on).days<=30
                            and _valid(code,claim.value,customer)):
                        row.update(state='FILLED_OWNER_REVIEWED_VALUE',value=claim.value,
                                   source={'type':'COMPANY_PROFILE_FACT','fact_id':fact.id,'customer_id':customer_id,
                                           'fact_key':fact.fact_key,'version':fact.version_no,'reference':fact.source_ref,
                                           'observed_on':claim.observed_on.isoformat()})
                    else:
                        row['state']='IDENTITY_SCOPE_OR_VALUE_UNCONFIRMED'
        results.append(row)
    return results


def _check_package(raw):
    if len(raw)>8*1024*1024:
        raise ValueError('Template too large')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        names=[i.filename for i in infos]
        if (len(infos)>1500 or len(names)!=len(set(names)) or sum(i.file_size for i in infos)>32*1024*1024
                or any(i.flag_bits&1 for i in infos)):
            raise ValueError('Unsafe or excessive template package')
        for name in names:
            n=name.lower()
            if any(x in n for x in ('vbaproject','activex/','embeddings/','externallinks/','_xmlsignatures/')):
                raise ValueError('Active or signed template not supported')
        for name in names:
            if name.endswith('.rels') and re.search(rb'TargetMode\s*=\s*["\']External["\']',z.read(name),re.IGNORECASE):
                raise ValueError('External template relationship not supported')


def _docx_fill(raw, fields, rows):
    document=Document(io.BytesIO(raw))
    runs=list({run._r:run for p in _iter_docx_paragraphs(document) for run in p.runs}.values())
    tokens={}
    for f,r in zip(fields,rows,strict=True):
        prefix='docx:token:'
        if f.target_locator!=prefix+f.expected_placeholder:
            raise ValueError('Invalid reviewed DOCX placeholder')
        token=f.expected_placeholder
        if token in tokens or any(token in t or t in token for t in tokens):
            raise ValueError('Duplicate or overlapping DOCX target')
        matches=[run for run in runs if token in run.text]
        if sum(run.text.count(token) for run in matches)!=1:
            raise ValueError('Reviewed token not unique in original template')
        tokens[token]=r['value']
    pattern=re.compile('|'.join(re.escape(t) for t in tokens))
    for run in runs:
        value=pattern.sub(lambda m:tokens[m.group()] if tokens[m.group()] is not None else m.group(),run.text)
        if value!=run.text:
            run.text=value
    out=io.BytesIO();document.save(out)
    return out.getvalue()


def _xlsx_fill(raw,fields,rows):
    book=load_workbook(io.BytesIO(raw),data_only=False,keep_links=False)
    seen=set()
    for f,r in zip(fields,rows,strict=True):
        if not f.target_locator.startswith('xlsx:cell:'):
            raise ValueError('Invalid reviewed XLSX target')
        sheet,coord=_parse_xlsx_locator(f.target_locator)
        if sheet not in book.sheetnames or (sheet,coord) in seen:
            raise ValueError('Unknown or duplicate normalized XLSX target')
        seen.add((sheet,coord))
        ws=book[sheet]
        _merged_anchor_or_fail(ws,coord)
        cell=ws[coord]
        if cell.data_type=='f' or cell.value!=f.expected_placeholder:
            raise ValueError('Reviewed XLSX placeholder changed or formula target')
        if r['value'] is not None:
            cell.value=r['value']
            cell.data_type='s'
    out=io.BytesIO();book.save(out);book.close()
    return out.getvalue()


def render_reviewed_identity_draft(session,*,customer_id,template_bytes:bytes,template_map:ReviewedTemplateMap,now=None):
    """Explicit mapping only; unknowns remain untouched. In-memory draft + receipt."""
    now=_utc(now or datetime.now(UTC))
    if not template_map.owner_reviewed_mapping or not template_map.map_review_ref.strip():
        raise ValueError('Explicit reviewed mapping required')
    actual=hashlib.sha256(template_bytes).hexdigest()
    if actual!=template_map.template_sha256:
        raise ValueError('Template differs from reviewed hash')
    _check_package(template_bytes)
    rows=_resolve(session,customer_id,template_map.fields,now)
    # A field value containing any reviewed placeholder is refused, even
    # though substitution is simultaneous; avoid confusing residual tokens.
    if any(r['value'] is not None and any(f.expected_placeholder in r['value'] for f in template_map.fields) for r in rows):
        raise ValueError('Identity value contains template placeholder')
    render=_docx_fill if template_map.format=='docx' else _xlsx_fill
    output=render(template_bytes,template_map.fields,rows)
    return output,{'status':'DRAFT_REVIEW_ONLY','customer_id':customer_id,'format':template_map.format,
                   'template_sha256':actual,'output_sha256':hashlib.sha256(output).hexdigest(),
                   'map_review_ref':template_map.map_review_ref,'fields':rows,
                   'filled_count':sum(r['value'] is not None for r in rows),
                   'unknown_count':sum(r['value'] is None for r in rows),
                   'mapping_exhaustive':False,'official_identity_verified':False,'application_ready':False,
                   'signature_performed':False,'submission_performed':False,'external_delivery_performed':False}
