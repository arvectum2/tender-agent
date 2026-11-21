import json
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

from scripts.price01.intake_reviewed_contracts import run
from src.tender_research import reviewed_contract_evidence as e


def make_row(i,price,qty,scope='Identical complete fixture specification'):
    number=str(i).zfill(19)
    fields={'signed_status':'SIGNED','registry':number,'contract_id':'fixture-'+str(i),
            'signed_date':'2026-01-01','currency':'RUB','price':price,'quantity':qty,
            'quantity_unit':'item','scope':scope,'tax':'VAT included','terms':'Fixed total price'}
    root=ET.Element('fixtureContract')
    row={}
    for idx,(k,v) in enumerate(fields.items()):
        ET.SubElement(root,k).text=v
        row[k]={'path':[idx],'tag':k,'text':v}
    raw=ET.tostring(root,encoding='utf-8')
    row.update(registry_number=number,source_sha256=e.digest(raw),
               source_url='https://zakupki.gov.ru/fixture/'+number,
               contract_number=fields['contract_id'],signed_on=fields['signed_date'],
               price_rub=price,contracted_quantity=qty,unit='item',full_scope=scope,
               tax_terms=fields['tax'],price_terms=fields['terms'],
               reviewer_confirms_signed_contract=True,
               reviewer_confirms_exact_quantity_covers_entire_price=True,
               review_note='Synthetic fixture, not actual EIS evidence.')
    return row,raw


@pytest.fixture
def bundle():
    a,x=make_row(1,'100.00','3')
    b,y=make_row(2,'200.00','4')
    c,z=make_row(3,'10.00','1','Different scope')
    return {'schema_version': 1,'review_id': 'fixture-review','reviewer': 'test reviewer',
                'reviewed_on': '2026-02-01','records': [a,b,c],
                'equivalent_registry_numbers': [a['registry_number'],b['registry_number']],
                'reference_registry_number': a['registry_number'],
                'scope_review_note': 'Synthetic exact scope review only.',
                'reviewer_confirms_full_scope_and_price_terms_equivalent': True},{
                    e.digest(x):x,e.digest(y):y,e.digest(z):z}


def raw_manifest(value):
    return json.dumps(value,ensure_ascii=False).encode()


def verify(value,originals):
    raw=raw_manifest(value)
    return e.intake(raw,expected_manifest_sha256=e.digest(raw),originals=originals)


def test_normalization(bundle,tmp_path):
    data,originals=bundle
    r=verify(data,originals)
    assert r['range_rub_per_unit']=={'minimum':'33.333333','median':'41.666667','maximum':'50.000000','distinct_procurements':2}
    assert len(r['observations'])==2
    assert all(r[k] is False for k in ('independent_signature_verification','source_authenticity_independently_verified','contract_execution_verified','completed_work_quantity_verified','inputs_stored','external_submission_allowed'))
    assert r['current_market_price'] is None and r['recommendation'] is None
    assert r['receipt_sha256']==e.sealed({k:v for k,v in r.items() if k!='receipt_sha256'})
    raw=raw_manifest(data);m=tmp_path/'review.json';m.write_bytes(raw)
    for sha,doc in originals.items():(tmp_path/(sha+'.xml')).write_bytes(doc)
    assert run(m,e.digest(raw),tmp_path)==r
    data['equivalent_registry_numbers']=data['equivalent_registry_numbers'][:1]
    assert verify(data,originals)['range_rub_per_unit'] is None


@pytest.mark.parametrize('mode',['different_scope','duplicate_procurement','duplicate_contract','duplicate_source','duplicate_choice','no_reference','false_review','false_signed','false_quantity','changed_price','wrong_anchor','wrong_tag','wrong_date','zero_quantity','float_price','foreign_url','wrong_tax','wrong_terms'])
def test_reject_claims(bundle,mode):
    data,originals=deepcopy(bundle)
    a,b,c=data['records']
    if mode=='different_scope':data['equivalent_registry_numbers'].append(c['registry_number'])
    elif mode=='duplicate_procurement':b['registry_number']=a['registry_number']
    elif mode=='duplicate_contract':b['contract_number']=a['contract_number']
    elif mode=='duplicate_source':b['source_sha256']=a['source_sha256']
    elif mode=='duplicate_choice':data['equivalent_registry_numbers'].append(a['registry_number'])
    elif mode=='no_reference':data['equivalent_registry_numbers']=[b['registry_number']]
    elif mode=='false_review':data['reviewer_confirms_full_scope_and_price_terms_equivalent']=False
    elif mode=='false_signed':a['reviewer_confirms_signed_contract']=False
    elif mode=='false_quantity':a['reviewer_confirms_exact_quantity_covers_entire_price']=False
    elif mode=='changed_price':a['price_rub']='999';a['price']['text']='999'
    elif mode=='wrong_anchor':a['price']['path']=[6]
    elif mode=='wrong_tag':a['price']['tag']='other'
    elif mode=='wrong_date':data['reviewed_on']='2025-12-31'
    elif mode=='zero_quantity':a['contracted_quantity']='0';a['quantity']['text']='0'
    elif mode=='float_price':a['price_rub']=100.0
    elif mode=='foreign_url':a['source_url']='https://zakupki.gov.ru.evil.invalid/foo'
    elif mode=='wrong_tax':b['tax_terms']='Tax excluded';b['tax']['text']='Tax excluded'
    elif mode=='wrong_terms':b['price_terms']='Variable price';b['terms']['text']='Variable price'
    with pytest.raises(ValueError):verify(data,originals)


def test_pins_and_originals(bundle,tmp_path):
    data,originals=bundle
    raw=raw_manifest(data)
    with pytest.raises(ValueError):e.intake(raw,expected_manifest_sha256='0'*64,originals=originals)
    with pytest.raises(ValueError):verify(data,{})
    bad=dict(originals);sha=data['records'][0]['source_sha256'];bad[sha]+=b' '
    with pytest.raises(ValueError):verify(data,bad)
    duplicate=raw.replace(b'"schema_version": 1',b'"schema_version": 1,"schema_version":1',1)
    with pytest.raises(ValueError):e.load_manifest(duplicate,e.digest(duplicate))
    for doc in (b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><x>&x;</x>',b'<x>'+b'<a>'*40+b'</a>'*40+b'</x>',b'x'*(e.MAX_SOURCE+1)):
        with pytest.raises(ValueError):e.parse_original(doc)
    m=tmp_path/'review.json';m.write_bytes(raw)
    for key,doc in originals.items():(tmp_path/(key+'.xml')).write_bytes(doc)
    (tmp_path/(sha+'.xml')).unlink()
    (tmp_path/(sha+'.xml')).symlink_to(m)
    with pytest.raises(OSError):run(m,e.digest(raw),tmp_path)


def test_reviewed_registry_append_withdraw_and_recompute(bundle,tmp_path,monkeypatch,capsysbinary):
    import sys

    from scripts.price01.prepare_contract_registry_release import main
    from src.tender_research import reviewed_contract_registry as reg

    data,originals=bundle
    empty=b'{"schema":"price01_reviewed_contract_registry_v1","events":[]}\n'
    old=reg.load_release(empty,e.digest(empty))
    assert reg.replay(old)==({},[])
    manifest=raw_manifest(data)
    group=reg.publication_group(manifest,e.digest(manifest),originals,'fixture-group')
    assert group.range_rub_per_unit.median=='41.666667'
    assert len(group.observations)==2
    assert 'source_url' not in group.observations[0].model_dump()
    assert group.full_scope==data['records'][0]['full_scope']
    raw=reg.append_candidate(old,action='PUBLISH',group_id=group.group_id,reason='Reviewed fixture publication',group=group)
    release=reg.load_release(raw,e.digest(raw));active,_=reg.replay(release)
    assert list(active)==['fixture-group']
    with pytest.raises(ValueError):reg.load_release(raw,e.digest(empty))
    for field,value in [('unit_price_rub','1.000000'),('signed_contract_price_rub','0')]:
        altered=group.model_dump();altered['observations'][0][field]=value
        with pytest.raises(ValueError):reg.Group.model_validate(altered)
    bad=group.model_dump();bad['range_rub_per_unit']['median']='42.000000'
    with pytest.raises(ValueError):reg.Group.model_validate(bad)
    # A new review pin must not silently double-count active source rows.
    duplicate=reg.Group.model_validate({**group.model_dump(),'group_id':'other-group','reviewed_manifest_sha256':'f'*64})
    with pytest.raises(ValueError):reg.append_candidate(release,action='PUBLISH',group_id=duplicate.group_id,reason='Duplicate source prohibited',group=duplicate)
    revoked=reg.append_candidate(release,action='WITHDRAW',group_id=group.group_id,reason='Explicit fixture withdrawal')
    after=reg.load_release(revoked,e.digest(revoked));active,withdrawn=reg.replay(after)
    assert not active and withdrawn[0]['revision']==2
    assert after.events[0]==release.events[0]
    assert after.events[1].previous_event_sha256==release.events[0].event_sha256
    with pytest.raises(ValueError):reg.append_candidate(after,action='WITHDRAW',group_id=group.group_id,reason='Already withdrawn fixture')
    with pytest.raises(ValueError):reg.append_candidate(after,action='PUBLISH',group_id=group.group_id,reason='Reused group prohibited',group=group)
    # A separate reviewed replacement can follow explicit withdrawal.
    replacement=reg.append_candidate(after,action='PUBLISH',group_id=duplicate.group_id,reason='Reviewed correction fixture',group=duplicate)
    assert list(reg.replay(reg.load_release(replacement,e.digest(replacement)))[0])==['other-group']
    # Hashing a broken chain does not make it valid.
    corrupted=json.loads(revoked);event=corrupted['events'][1];event['previous_event_sha256']='0'*64
    event['event_sha256']=e.sealed({k:v for k,v in event.items() if k!='event_sha256'})
    b=raw_manifest(corrupted)
    with pytest.raises(ValueError):reg.load_release(b,e.digest(b))
    release_path=tmp_path/'release.json';release_path.write_bytes(empty)
    manifest_path=tmp_path/'review.json';manifest_path.write_bytes(manifest)
    for key,doc in originals.items():(tmp_path/(key+'.xml')).write_bytes(doc)
    monkeypatch.setattr(sys,'argv',['prepare','--release',str(release_path),'--release-sha256',e.digest(empty),'--action','PUBLISH','--group-id','fixture-group','--reason','Reviewed fixture publication','--manifest',str(manifest_path),'--reviewed-sha256',e.digest(manifest),'--originals',str(tmp_path)])
    main()
    assert capsysbinary.readouterr().out==raw
    assert release_path.read_bytes()==empty


def test_price01_release_client_pins_and_default_gates():
    """A reviewed source update must change both client pins in the same release."""
    import re
    from pathlib import Path

    from src.modules.saas_foundation import company_reviewed_contracts as c
    from src.shared.config.settings import Settings
    from src.tender_research import reviewed_contract_registry as reg

    root=Path(__file__).resolve().parents[2]
    release=c._approved_release()
    projection=e.sealed(reg.public_projection(release,c._RELEASE_SHA256))
    web=(root/'src/modules/saas_foundation/ui.py').read_text()
    swift=(root/'ios/TenderAgent/TenderAgentApp/Networking/CompanyAPIClient.swift').read_text()
    for name,value in [('reviewedReleasePin',c._RELEASE_SHA256),('reviewedProjectionPin',projection)]:
        assert re.findall(r"\b"+name+r"='([a-f0-9]{64})'",web)==[value]
    for name,value in [('releasePin',c._RELEASE_SHA256),('projectionPin',projection)]:
        assert re.findall(r'\bstatic let '+name+r'="([a-f0-9]{64})"',swift)==[value]
    from scripts.acceptance.run_price01_staging import FLAGS

    assert Settings.model_fields['saas_foundation_enabled'].default is False
    for flag in FLAGS:
        assert Settings.model_fields['saas_company_'+flag+'_enabled'].default is False
