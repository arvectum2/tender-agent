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


def publish_fixture(root,receipt,label='Synthetic fixture'):
    raw=raw_manifest(receipt)
    file_sha=e.digest(raw)
    directory=root/'receipts';directory.mkdir(exist_ok=True)
    (directory/(file_sha+'.json')).write_bytes(raw)
    return {'review_id':receipt['review_id'],'reviewed_manifest_sha256':receipt['reviewed_manifest_sha256'],
            'receipt_file_sha256':file_sha,'receipt_sha256':receipt['receipt_sha256'],'public_scope_label':label}


def release_fixture(root,version,previous,entries,**changes):
    directory=root/'releases';directory.mkdir(exist_ok=True)
    value={'schema':'reviewed_contract_registry_release_v1','version':version,'previous_release_sha256':previous,
           'published_on':'2026-11-17','entries':entries,**changes}
    raw=raw_manifest(value)
    (directory/f'{version:04d}.json').write_bytes(raw)
    return e.digest(raw)


def test_registry_publication_chain(bundle,tmp_path):
    from src.tender_research import reviewed_contract_registry as reg

    data,originals=bundle
    assert reg.load_registry()['groups']==[]
    receipt=verify(data,originals)
    entry=publish_fixture(tmp_path,receipt)
    first=release_fixture(tmp_path,1,None,[])
    second=release_fixture(tmp_path,2,first,[entry])
    third=release_fixture(tmp_path,3,second,[])
    group=reg.load_registry(tmp_path,(first,second))['groups'][0]
    assert group['range_rub_per_unit']==receipt['range_rub_per_unit']
    assert group['reviewed_manifest_sha256']==receipt['reviewed_manifest_sha256']
    assert group['receipt_sha256']==receipt['receipt_sha256']
    assert 'scope_review_note' not in group
    assert all('source_url' not in o for o in group['observations'])
    registry=reg.load_registry(tmp_path,(first,second,third))
    assert registry['groups']==[]
    assert [r['active_groups_count'] for r in registry['release_history']]==[0,1,0]
    assert registry['release']['version']==3
    assert registry['recommendation'] is None
    (tmp_path/'receipts'/(entry['receipt_file_sha256']+'.json')).write_bytes(b'{}')
    # Even removed groups must retain their previously pinned audit evidence.
    with pytest.raises(ValueError):reg.load_registry(tmp_path,(first,second,third))


@pytest.mark.parametrize('mode',['wrong_release_pin','broken_parent','wrong_manifest','wrong_receipt','wrong_group','changed_identity','overlap','rewritten_price','rewritten_range','false_authenticity','numeric_bool','future_contract','symlink'])
def test_registry_rejects_invalid_publication(bundle,tmp_path,mode):
    from src.tender_research import reviewed_contract_registry as reg

    data,originals=bundle
    receipt=verify(data,originals)
    entry=publish_fixture(tmp_path,receipt)
    first=release_fixture(tmp_path,1,None,[entry])
    entries=[entry]
    previous=first
    if mode=='wrong_release_pin':
        with pytest.raises(ValueError):reg.load_registry(tmp_path,('0'*64,))
        return
    if mode=='broken_parent':previous='0'*64
    elif mode=='wrong_manifest':entries=[{**entry,'reviewed_manifest_sha256':'0'*64}]
    elif mode=='wrong_receipt':entries=[{**entry,'receipt_sha256':'0'*64}]
    elif mode=='wrong_group':entries=[{**entry,'review_id':'another-review'}]
    elif mode=='changed_identity':entries=[{**entry,'public_scope_label':'Changed existing label'}]
    elif mode=='overlap':
        data['review_id']='second-review'
        other=publish_fixture(tmp_path,verify(data,originals))
        entries=[entry,other]
    elif mode in ('rewritten_price','rewritten_range','false_authenticity','numeric_bool','future_contract'):
        altered=deepcopy(receipt);altered['review_id']='second-review'
        if mode=='rewritten_price':altered['observations'][0]['unit_price_rub']='99.000000'
        elif mode=='rewritten_range':altered['range_rub_per_unit']['median']='99.000000'
        elif mode=='false_authenticity':altered['source_authenticity_independently_verified']=True
        elif mode=='numeric_bool':altered['inputs_stored']=0
        elif mode=='future_contract':altered['observations'][0]['signed_on']='2027-01-01'
        altered['receipt_sha256']=e.sealed({k:v for k,v in altered.items() if k!='receipt_sha256'})
        entries=[publish_fixture(tmp_path,altered)]
    elif mode=='symlink':
        p=tmp_path/'receipts'/(entry['receipt_file_sha256']+'.json')
        other=tmp_path/'outside.json';p.rename(other);p.symlink_to(other)
    second=release_fixture(tmp_path,2,previous,entries)
    with pytest.raises((ValueError,OSError)):reg.load_registry(tmp_path,(first,second))
