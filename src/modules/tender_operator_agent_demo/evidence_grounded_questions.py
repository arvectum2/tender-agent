"""Conservative Russian-language intent routing over existing evidence paths."""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from src.modules.tender_operator_agent_demo.evidence_copilot import (
    EvidenceQuestion,
    answer_question,
)
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    DocumentSearchQuestion,
    checked_search_run,
    search_run_documents,
)


class GroundedQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=240)


# Entire-question matching: never silently discard a second question or legal qualifier.
_FACTS = {
    'subject': r'(?:каков предмет закупки|что закупают|что закупается|что является предметом закупки)',
    'nmck': r'(?:какова нмцк|какая нмцк|сколько составляет нмцк|какая начальная максимальная цена контракта)',
    'deadline': r'(?:каков архивный срок подачи заявок|когда заканчивается подача заявок|до какого числа принимают заявки|какой срок подачи заявок)',
}
_TOPICS = {
    'payment': (r'(?:какие условия оплаты(?: работ)?|как оплачиваются работы|какой срок оплаты(?: работ)?|когда оплачиваются работы)', 'оплата работ', 'Условия оплаты'),
    'delivery': (r'(?:какие сроки выполнения работ|каков срок исполнения контракта|какой срок поставки|когда должны быть выполнены работы)', 'срок выполнения работ', 'Сроки исполнения'),
    'security': (r'(?:какие условия обеспечения контракта|какие требования к обеспечению исполнения контракта)', 'обеспечение контракта', 'Условия обеспечения контракта'),
    'bid_security': (r'(?:что сказано об обеспечении заявки|какие условия обеспечения заявки)', 'обеспечение заявки', 'Условия обеспечения заявки'),
    'service_payment': (r'(?:какие условия оплаты услуг|какой срок оплаты услуг)', 'оплата услуг', 'Условия оплаты услуг'),
}
_PERCENT = re.compile(r'сколько составляет ([0-9]{1,3}(?:[.,][0-9]{1,4})?)\s*%\s*(?:от )?нмцк\Z')


def answer_grounded_question(run_id: str, request: GroundedQuestion) -> dict:
    checked_search_run(run_id)
    q = re.sub(r'\s+', ' ', request.question.strip().casefold()).removesuffix('?').strip()
    result = {'contract': 'apr08_grounded_question_v1', 'run_id': run_id, 'status': 'UNKNOWN',
              'intent': None, 'answer': None, 'citations': [], 'citation_kind': None, 'calculation': None,
              'scope_complete': False, 'semantic_answer_verified': False, 'bid_ready': False,
              'current_revision_attested': False, 'legal_requirement_attested': False,
              'requires_human_review': True, 'external_action_allowed': False}
    intent = next((k for k, pattern in _FACTS.items() if re.fullmatch(pattern, q)), None)
    pct = _PERCENT.fullmatch(q)
    if pct:
        from pydantic import ValidationError

        try:
            fact_request = EvidenceQuestion(question='nmck_percent', percent=pct[1].replace(',', '.'))
        except ValidationError:
            return {**result, 'reason': 'INVALID_EXPLICIT_PERCENT'}
        intent = 'nmck_percent'
    elif intent:
        fact_request = EvidenceQuestion(question=intent)
    if intent:
        fact = answer_question(run_id, fact_request)
        if fact['status'] not in ('ARCHIVED_SOURCE_FACT', 'HYPOTHETICAL_CALCULATION'):
            return {**result, 'intent': intent, 'reason': fact.get('reason', 'SOURCE_FIELD_UNVERIFIED')}
        return {**result, 'intent': intent, 'status': fact['status'], 'answer': fact['answer'],
                'citations': fact['citations'], 'citation_kind': 'ARCHIVED_XML', 'calculation': fact['calculation']}
    topic = next(((key, terms, title) for key, (pattern, terms, title) in _TOPICS.items() if re.fullmatch(pattern, q)), None)
    if topic is None:
        return {**result, 'reason': 'UNSUPPORTED_OR_COMPOUND_QUESTION'}
    key, terms, title = topic
    found = search_run_documents(run_id, DocumentSearchQuestion(query=terms))
    if found['status'] != 'VERIFIED_EXCERPTS_ONLY' or not found['citations']:
        return {**result, 'intent': key, 'reason': 'NO_VERIFIED_TOPIC_EXCERPT'}
    return {**result, 'intent': key, 'status': 'TOPIC_EXCERPTS_ONLY', 'citation_kind': 'ORIGINAL_DP_CHUNK',
            'answer': f'{title}: найдены проверенные фрагменты. Их применимость и полнота требуют проверки.',
            'citations': found['citations']}
