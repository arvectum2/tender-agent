import pytest

from src.modules.tender_operator_agent_demo.ri223_linked_contract import (
    _PARAGRAPHS,
    _SOURCE_SHA,
    linked_contract_observation,
    paragraph_parts,
)

LINEAGE={'member_sha256':_SOURCE_SHA,'member_path':'pinned.docx'}
SCENARIO={'status':'ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY','calculation':{'offer_scenario':{
    'offer_price_rub':'900000.00','economic_profit_rub':'222000.00'}}}


def review(missing=(), mismatch=False, scenario=SCENARIO):
    missing_quotes={q for x in missing for q in paragraph_parts(x,_PARAGRAPHS[x])}
    def verify(**kw):
        quote=kw['exact_quote']
        if quote in missing_quotes:
            return {'status':'unverified','evidence':None}
        return {'status':'literal_quote_found_in_extracted_original_only','evidence':{
            'original_sha256':'b'*64 if mismatch else _SOURCE_SHA,'ri223_container':LINEAGE,
            'file_id':kw['file_id'],'quote':quote,'chunk_id':'c'}}
    return linked_contract_observation('test','FILE-01',LINEAGE,scenario,verifier=verify)


def test_conditional_timing_and_economics():
    result=review()
    assert all(g['status']=='VERIFIED_REVIEWED_PARAGRAPH_GROUP' for g in result['groups'].values())
    t=result['payment_sequence']
    assert t['illustrative_no_refusal_working_days']==17
    assert t['actual_cash_gap_days'] is None and t['guaranteed_maximum_days'] is None
    s={x['code']:x for x in result['scenario_sensitivity']}
    assert s['DELAY_10']['profit_less_assumed_penalty_rub']=='213000.00'
    assert s['DELAY_11']['modeled_penalty_rub']=='9900.00'
    assert not s['DELAY_10']['termination_right_scenario'] and s['DELAY_11']['termination_right_scenario']
    assert s['UNAUTHORIZED_ASSIGNMENT']['profit_less_assumed_penalty_rub']=='42000.00'
    assert not result['whole_contract_complete'] and not result['go_eligible']
    assert not result['aggregate_penalty_attested']


@pytest.mark.parametrize('section',['3.4','4.3','4.4'])
def test_incomplete_payment_group_refuses_timing(section):
    assert review(missing=(section,))['payment_sequence'] is None


@pytest.mark.parametrize('section',['5.3','5.4','5.6'])
def test_incomplete_penalty_group_refuses_scenario(section):
    s=review(missing=(section,))['scenario_sensitivity']
    assert all(x['code']!='UNAUTHORIZED_ASSIGNMENT' if section=='5.6' else not x['code'].startswith('DELAY_') for x in s)


def test_source_mismatch_and_missing_economics():
    r=review(mismatch=True)
    assert r['payment_sequence'] is None and not r['scenario_sensitivity']
    assert not review(scenario={})['scenario_sensitivity']

def test_partitions_cover_full_pinned_source():
    for section,quote in _PARAGRAPHS.items():
        parts=paragraph_parts(section,quote)
        assert ' '.join(parts)==quote
    assert len(paragraph_parts('4.3',_PARAGRAPHS['4.3']))==2
    assert len(paragraph_parts('5.3',_PARAGRAPHS['5.3']))==2


def test_single_missing_fragment_refuses_complete_paragraph():
    missing=paragraph_parts('4.3',_PARAGRAPHS['4.3'])[1]
    def verify(**kw):
        q=kw['exact_quote']
        if q==missing:
            return {'status':'unverified','evidence':None}
        return {'status':'literal_quote_found_in_extracted_original_only','evidence':{
            'original_sha256':_SOURCE_SHA,'ri223_container':LINEAGE,'file_id':kw['file_id'],'quote':q,'chunk_id':'c'}}
    result=linked_contract_observation('test','FILE-01',LINEAGE,SCENARIO,verifier=verify)
    assert result['payment_sequence'] is None
    assert '4.3' not in result['groups']['acceptance_payment']['source_sections']
