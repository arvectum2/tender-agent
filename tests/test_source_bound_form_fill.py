"""Independent synthetic owner facts and real in-memory OOXML round trips."""
import hashlib
import io
from datetime import UTC, datetime, timedelta

import pytest
from docx import Document
from openpyxl import Workbook, load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.modules.application_package_generator.source_bound_fill import (
    ReviewedTemplateMap,
    render_reviewed_identity_draft,
)
from src.modules.company_profile_store.models import CompanyProfileFactVersion
from src.modules.customer_registry.models import CustomerProfile
from src.shared.db import models as _models  # noqa: F401
from src.shared.db.base import Base

NOW=datetime(2026,11,18,10,tzinfo=UTC)


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([CustomerProfile(customer_id='fixture-a',legal_name='Example A',inn='1234567890',kpp='123456789',customer_status='PROSPECT'),
                   CustomerProfile(customer_id='fixture-b',legal_name='Example B',inn='9876543210',kpp='987654321',customer_status='PROSPECT')])
        s.commit()
        yield s
    engine.dispose()


def fact(s,code,value,*,version=1,customer='fixture-a',inn='1234567890',source='OWNER_CONFIRMED',observed='2026-11-18',expires=NOW+timedelta(days=30)):
    r=CompanyProfileFactVersion(customer_id=customer,fact_key='draft_identity:'+code,fact_group='IDENTITY',
        version_no=version,value_json={'schema_version':'draft-identity-value-v1','inn':inn,'field_code':code,
                                      'value':value,'observed_on':observed,'owner_confirmed':True},
        source_type=source,source_ref='synthetic-review:'+code,expires_at=expires,created_at=NOW)
    s.add(r);s.commit();return r.id


def template(fmt):
    stream=io.BytesIO()
    if fmt=='docx':
        d=Document();p=d.add_paragraph();p.add_run('Name: ')
        run=p.add_run('{{NAME}}');run.bold=True
        d.add_paragraph('INN: {{INN}}')
        d.add_paragraph('Declaration remains blank: ______')
        d.save(stream)
        locators=['docx:token:{{NAME}}','docx:token:{{INN}}']
    else:
        b=Workbook();w=b.active;w.title='Form'
        w['A1']='{{NAME}}';w['A1'].font=w['A1'].font.copy(bold=True)
        w['A2']='{{INN}}';w['B1']='=SUM(1,2)';w['B2']='Declaration remains blank: ______'
        b.save(stream);b.close();locators=['xlsx:cell:Form!A1','xlsx:cell:Form!A2']
    raw=stream.getvalue()
    m=ReviewedTemplateMap(template_sha256=hashlib.sha256(raw).hexdigest(),format=fmt,map_review_ref='synthetic-map-v1',
        owner_reviewed_mapping=True,fields=[{'field_code':code,'target_locator':loc,'expected_placeholder':token}
            for code,loc,token in zip(['legal_name','inn'],locators,['{{NAME}}','{{INN}}'],strict=True)])
    return raw,m


def render(s,raw,m,customer='fixture-a'):
    return render_reviewed_identity_draft(s,customer_id=customer,template_bytes=raw,template_map=m,now=NOW)


@pytest.mark.parametrize('fmt',['docx','xlsx'])
def test_roundtrip_and_unknown(db,fmt):
    raw,m=template(fmt);original=hashlib.sha256(raw).hexdigest()
    fid=fact(db,'legal_name','Example A')
    output,receipt=render(db,raw,m)
    assert receipt['filled_count']==1 and receipt['unknown_count']==1
    assert receipt['template_sha256']==original==hashlib.sha256(raw).hexdigest()
    assert receipt['output_sha256']==hashlib.sha256(output).hexdigest()
    assert receipt['fields'][0]['source']['fact_id']==fid
    assert receipt['fields'][0]['source']['version']==1
    assert receipt['fields'][1]['source'] is None
    assert not receipt['application_ready'] and not receipt['signature_performed']
    assert not receipt['submission_performed'] and not receipt['external_delivery_performed']
    if fmt=='docx':
        d=Document(io.BytesIO(output));assert d.paragraphs[0].runs[1].text=='Example A'
        assert d.paragraphs[0].runs[1].bold
        assert '{{INN}}' in d.paragraphs[1].text and d.paragraphs[2].text.endswith('______')
    else:
        b=load_workbook(io.BytesIO(output));w=b['Form']
        assert w['A1'].value=='Example A' and w['A1'].font.bold
        assert w['A2'].value=='{{INN}}' and w['B1'].value=='=SUM(1,2)'
        assert w['B2'].value.endswith('______')
    assert render(db,raw,m,'fixture-b')[1]['filled_count']==0


@pytest.mark.parametrize('bad',['expiry','foreign','wrong_value','unreviewed','future','historical'])
def test_latest_failure_no_fallback(db,bad):
    raw,m=template('docx');fact(db,'legal_name','Example A')
    options={};value='Example A'
    if bad=='expiry':options['expires']=NOW
    elif bad=='foreign':options['inn']='9876543210'
    elif bad=='wrong_value':value='Example B'
    elif bad=='unreviewed':options['source']='CUSTOMER_PROVIDED'
    elif bad=='future':options['observed']='2026-11-19'
    elif bad=='historical':options['observed']='2026-06-24'
    fact(db,'legal_name',value,version=2,**options)
    assert render(db,raw,m)[1]['filled_count']==0


def test_numeric_identity_remains_text(db):
    raw,m=template('xlsx');fact(db,'inn','1234567890')
    output,receipt=render(db,raw,m)
    c=load_workbook(io.BytesIO(output))['Form']['A2']
    assert c.value=='1234567890' and c.data_type=='s'
    assert receipt['filled_count']==1


@pytest.mark.parametrize('change',['hash','unreviewed','duplicate','wrong_placeholder','overlap','formula'])
def test_invalid_template_map(db,change):
    raw,m=template('xlsx' if change=='formula' else 'docx')
    d=m.model_dump()
    if change=='hash':d['template_sha256']='0'*64
    elif change=='unreviewed':d['owner_reviewed_mapping']=False
    elif change=='duplicate':d['fields'].append(d['fields'][0])
    elif change=='wrong_placeholder':d['fields'][0]['expected_placeholder']='unknown'
    elif change=='overlap':d['fields'][1].update(target_locator='docx:token:NAME',expected_placeholder='NAME')
    elif change=='formula':d['fields'][0].update(target_locator='xlsx:cell:Form!B1',expected_placeholder='=SUM(1,2)')
    with pytest.raises(ValueError):
        render(db,raw,ReviewedTemplateMap.model_validate(d))


@pytest.mark.parametrize('value',['=SUM(1,2)','+123','@formula','Example A\nOther'])
def test_unsafe_identity_text_not_filled(db,value):
    raw,m=template('xlsx')
    d=m.model_dump();d['fields'][0]['field_code']='legal_address'
    fact(db,'legal_address',value)
    out,receipt=render(db,raw,ReviewedTemplateMap.model_validate(d))
    assert receipt['filled_count']==0
    assert load_workbook(io.BytesIO(out))['Form']['A1'].value=='{{NAME}}'


def test_external_relationship_refused(db):
    import zipfile
    raw,m=template('docx')
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as base,zipfile.ZipFile(out,'w') as target:
        for item in base.infolist():
            target.writestr(item,base.read(item.filename))
        target.writestr('word/_rels/extra.xml.rels',
                        '<Relationships><Relationship TargetMode="External" Target="https://example.invalid"/></Relationships>')
    altered=out.getvalue()
    d=m.model_dump();d['template_sha256']=hashlib.sha256(altered).hexdigest()
    with pytest.raises(ValueError,match='External'):
        render(db,altered,ReviewedTemplateMap.model_validate(d))


def test_receipt_retains_latest_version(db):
    raw,m=template('docx')
    fact(db,'legal_name','Example A')
    fid=fact(db,'legal_name','Example A',version=2)
    _,receipt=render(db,raw,m)
    assert receipt['fields'][0]['source']['fact_id']==fid
    assert receipt['fields'][0]['source']['version']==2
