from pathlib import Path

from scripts.run_tender_operator_pilot import _read_operator_profile
from src.modules.tender_operator_agent_demo.decision_core import build_decision_core


def test_fixture_operator_profile_is_structured_for_decision_core():
    operator_dir = Path('tests/fixtures/local_pilot_runs/tender_operator_001')
    parsed = _read_operator_profile(operator_dir)
    profile = parsed['supplier_profile']
    assert profile['criteria']['categories'] == [
        'Industrial control equipment', 'Electrical distribution equipment', 'Automation systems'
    ]
    assert profile['criteria']['regions'] == ['Russian Federation (all regions)']
    assert profile['criteria']['price_min'] == 1_000_000
    assert profile['criteria']['price_max'] == 50_000_000
    assert profile['commercial']['vat_mode'] == 'with_vat'
    assert profile['commercial']['target_margin_percent'] == 15
    assert profile['commercial']['max_payment_delay_days'] == 45
    assert profile['commercial']['max_contract_security_percent'] == 30

    model = {
        'nmck': 5_000_000,
        'field_evidence': {'nmck': ['eis_notice:nmck']},
        'contract_draft_status': 'missing',
    }
    decision = build_decision_core(model, supplier_profile=profile)
    readiness = {row['code']: row for row in decision['readiness']}
    assert readiness['SUPPLIER_PROFILE']['status'] == 'SATISFIED'
    assert readiness['SUPPLIER_PRICE_RANGE']['status'] == 'SATISFIED'


def test_missing_or_malformed_profile_values_fail_closed(tmp_path):
    (tmp_path / 'operator_profile.md').write_text(
        '# Operator Profile\n\n## Target NMCK Range\n- Minimum: unknown\n- Maximum:\n\n'
        '## Financial Constraints\n- Target margin: n/a\n', encoding='utf-8'
    )
    profile = _read_operator_profile(tmp_path)['supplier_profile']
    assert profile['criteria']['price_min'] is None
    assert profile['criteria']['price_max'] is None
    assert profile['commercial']['target_margin_percent'] is None
