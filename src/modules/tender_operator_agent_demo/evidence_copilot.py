"""Bounded APR08 archived-source assistant, not general semantic or legal Q&A."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.modules.tender_operator_agent_demo.operator_workspace_evidence import (
    get_operator_source_evidence,
)

FIELDS = {'subject': 'procurement_title', 'nmck': 'nmck', 'deadline': 'application_deadline', 'nmck_percent': 'nmck'}


class EvidenceQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=200)
    percent: str | None = Field(default=None, pattern=r'^(?:[0-9]{1,2}(?:\.[0-9]{1,4})?|100(?:\.0{1,4})?)$')


def answer_question(run_id: str, request: EvidenceQuestion) -> dict:
    source = get_operator_source_evidence(run_id)
    result = {'contract': 'apr08_archived_source_answer_v1', 'run_id': run_id,
              'registry_number': source.get('registry_number'), 'question': request.question,
              'status': 'UNKNOWN', 'answer': None, 'citations': [], 'calculation': None,
              'source_selection': source.get('source_selection'), 'current_revision_attested': False,
              'legal_requirement_attested': False, 'bid_ready': False, 'external_action_allowed': False,
              'requires_human_review': True}
    if request.question not in FIELDS:
        return {**result, 'reason': 'UNSUPPORTED_QUESTION'}
    if (request.question == 'nmck_percent') != (request.percent is not None):
        return {**result, 'reason': 'EXPLICIT_PERCENT_REQUIRED_ONLY_FOR_CALCULATION'}
    if (source.get('run_id') != run_id or source.get('source_selection') != 'pinned_latest_archived_notice_revision'
            or source.get('source') != 'zakupki_gov_ru_getdocs_ip'):
        return {**result, 'reason': 'PINNED_ARCHIVED_SOURCE_REQUIRED'}
    fact = source.get('facts', {}).get(FIELDS[request.question], {})
    cites = fact.get('evidence') or []
    if (fact.get('status') != 'KNOWN' or len(cites) != 1 or not isinstance(cites[0], dict)
            or not all(cites[0].get(k) for k in ('file_id', 'source_ref', 'document', 'locator', 'excerpt'))):
        return {**result, 'reason': 'SOURCE_FIELD_UNVERIFIED'}
    excerpt = cites[0]['excerpt']
    if not isinstance(excerpt, str):
        return {**result, 'reason': 'SOURCE_FIELD_UNVERIFIED'}
    if request.question in ('nmck', 'nmck_percent') and not re.fullmatch(r'[0-9]{1,20}(?:\.[0-9]{1,2})?', excerpt):
        return {**result, 'reason': 'EXACT_DECIMAL_AMOUNT_REQUIRED'}
    if request.question == 'nmck_percent':
        base, rate = Decimal(excerpt), Decimal(request.percent)
        amount = (base * rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return {**result, 'status': 'HYPOTHETICAL_CALCULATION', 'answer': str(amount), 'citations': cites,
                'calculation': {'base_amount': format(base, 'f'), 'percent_user_assumption': format(rate, 'f'),
                                'formula': 'base_amount * percent / 100', 'rounding': 'ROUND_HALF_UP_2_DECIMALS',
                                'currency': None, 'actual_security_requirement': None}}
    return {**result, 'status': 'ARCHIVED_SOURCE_FACT', 'answer': excerpt, 'citations': cites}
