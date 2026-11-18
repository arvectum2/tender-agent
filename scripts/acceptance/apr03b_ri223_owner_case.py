"""Real source + explicitly synthetic costs; no real company economics assertion."""
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)
from src.modules.tender_operator_agent_demo.ri223_owner_review import (
    review_archived_owner_run,
)


def replay_owner(run):
    baseline=review_archived_owner_run(run)
    assert baseline['status']=='ARCHIVED_OWNER_REVIEW_ONLY'
    assert baseline['participant_sme_clause']['status']=='ARCHIVED_CUSTOMER_PARTICIPANT_SME_CLAUSE',baseline['participant_sme_clause']
    assert baseline['participant_sme_clause']['supplier_membership']=='UNKNOWN'
    assert baseline['historical_reference_list']['historical_completed_count']==0
    assert baseline['historical_reference_list']['current_reference_count'] is None
    assert baseline['scoring']['completed_contracts_weight_percent'] is None
    assert baseline['economics']['status']=='UNKNOWN'
    assert baseline['current_profile_binding']=='NOT_ESTABLISHED'
    inputs=ExplicitCostScenarioRequest(external_direct_rub='250000',labor_rub='300000',
        reserve_rub='50000',fixed_platform_fees_rub='10000',revenue_tax_percent='6',
        variable_platform_fee_percent='1',target_profit_rub='100000',
        offer_scenario={'offer_price_rub':'900000','nonrefundable_guarantee_fees_rub':'5000',
                        'refundable_bid_cash_rub':'20000','refundable_contract_cash_rub':'100000'},
        accept_hypothetical_assumptions_only=True)
    out=review_archived_owner_run(run,inputs)
    assert out['status']=='ARCHIVED_OWNER_REVIEW_ONLY' and not out['go_eligible']
    assert out['decision']=='NOT_DECIDED' and out['competitive_recommendation']=='NOT_ASSESSED'
    risks=out['contract_risk'];print('RI223_CONTRACT_RISK_ACTUAL',risks['status'],risks.get('verified_clause_count'),[(x['clause'],x['status']) for x in risks['clauses']],risks.get('scenario_exposure'),flush=True)
    assert risks['status']=='ARCHIVED_CONTRACT_CLAUSE_REVIEW_ONLY' and risks['verified_clause_count']==14
    assert risks['scenario_exposure']['daily_delay_penalty_rub']=='900.00'
    assert risks['scenario_exposure']['delay_10_days_rub']=='9000.00'
    assert risks['scenario_exposure']['unauthorized_assignment_penalty_rub']=='180000.00'
    assert risks['liability_cap_rub'] is None and not risks['go_eligible']
    ec=out['economics'];cell=ec['calculation']['offer_scenario']
    assert ec['archived_lot_initial_sum_rub']=='1020000' and ec['offer_within_archived_initial_sum']
    assert cell['economic_profit_rub']=='222000.00' and cell['pre_receipt_stress_cash_rub']=='498000.00'
    assert not ec['actual_costs_verified'] and cell['actual_security_requirement_rub'] is None
    assert ec['target_threshold_within_archived_initial_sum']
    print('RI223_OWNER_ACTUAL_SOURCE_PASS SME participant quote; historical owner 0, current UNKNOWN; synthetic economics',ec['calculation']['full_cost_plus_explicit_target_rub'],cell['economic_profit_rub'],cell['pre_receipt_stress_cash_rub'],flush=True)
