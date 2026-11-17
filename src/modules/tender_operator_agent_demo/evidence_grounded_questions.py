"""Conservative Russian-language intent routing over existing evidence paths."""
from __future__ import annotations

import re
from functools import partial

from pydantic import BaseModel, ConfigDict, Field

from src.modules.tender_operator_agent_demo.evidence_copilot import (
    EvidenceQuestion,
    answer_question,
)
from src.modules.tender_operator_agent_demo.evidence_delivery_observation import (
    delivery_candidate,
    literal_delivery_observation,
)
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    DocumentSearchQuestion,
    checked_search_run,
    search_run_documents,
)
from src.modules.tender_operator_agent_demo.evidence_legal_reference import (
    legal_reference_observation,
)
from src.modules.tender_operator_agent_demo.evidence_payment_observation import (
    literal_payment_observation,
    payment_candidate,
)
from src.modules.tender_operator_agent_demo.evidence_security_observation import (
    archived_security_observation,
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
              'intent': None, 'answer': None, 'citations': [], 'citation_kind': None, 'calculation': None, 'observation': None,
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
    legal_kind = next((kind for kind, pattern in {
        'bid_security': r'(?:поясни требования к обеспечению заявки|какие нормы указаны для обеспечения заявки)',
        'contract_security': r'(?:поясни требования к обеспечению исполнения контракта|какие нормы указаны для обеспечения исполнения контракта)',
    }.items() if re.fullmatch(pattern, q)), None)
    if legal_kind:
        observation = legal_reference_observation(run_id, legal_kind)
        if observation['status'] != 'CUSTOMER_TERMS_LEGAL_REFERENCES':
            return {**result, 'intent': 'legal_reference', 'reason': observation['reason']}
        return {**result, 'intent': 'legal_reference', 'status': observation['status'], 'observation': observation,
                'citations': observation['citations'], 'citation_kind': 'ARCHIVED_XML',
                'answer': 'Текст заказчика проверен по архивному XML. Указанные ссылки на нормы не являются независимой проверкой законодательства.'}
    security_kind = next((kind for kind, pattern in {
        'bid_security': r'(?:какой размер обеспечения заявки|сколько составляет обеспечение заявки)',
        'contract_security': r'(?:какой размер обеспечения исполнения контракта|сколько составляет обеспечение исполнения контракта)',
    }.items() if re.fullmatch(pattern, q)), None)
    if security_kind:
        observation = archived_security_observation(run_id, security_kind)
        if observation['status'] != 'ARCHIVED_SECURITY_FIELDS':
            return {**result, 'intent': security_kind, 'reason': observation['reason']}
        return {**result, 'intent': security_kind, 'status': 'ARCHIVED_SECURITY_FIELDS',
                'observation': observation, 'citations': observation['citations'], 'citation_kind': 'ARCHIVED_XML',
                'answer': 'Явные поля архивного извещения. Фактический применимый размер и база расчёта не подтверждены.'}
    if re.fullmatch(r'(?:какой срок оплаты(?: работ| услуг)?|каков срок оплаты(?: работ| услуг)?)', q):
        kind = 'works' if q.endswith(' работ') else 'services' if q.endswith(' услуг') else None
        found = search_run_documents(run_id, DocumentSearchQuestion(query='оплата'),
                                     candidate_selector=partial(payment_candidate, object_kind=kind))
        citations = found['citations']
        # Even two identical durations may have different triggers; do not collapse.
        if found['status'] == 'VERIFIED_EXCERPTS_ONLY' and len(citations) == 1:
            observation = literal_payment_observation(citations[0]['quote'])
            if observation:
                return {**result, 'intent': 'payment_duration', 'status': 'LITERAL_PAYMENT_OBSERVATION',
                        'citation_kind': 'ORIGINAL_DP_CHUNK', 'observation': observation, 'citations': citations,
                        'answer': 'В найденном фрагменте указан срок оплаты. Это не подтверждение применимого срока; условия, исключения и связанные пункты требуют проверки.'}
        return {**result, 'intent': 'payment_duration', 'reason': 'NO_UNAMBIGUOUS_VERIFIED_PAYMENT_PARAGRAPH',
                'citations': citations, 'citation_kind': 'ORIGINAL_DP_CHUNK' if citations else None}
    performance_kind = next((kind for kind, pattern in {
        'services': r'(?:какой срок оказания услуг|каков срок оказания услуг|какие сроки оказания услуг)',
        'works': r'(?:какой срок выполнения работ|каков срок выполнения работ|какие сроки выполнения работ|когда должны быть выполнены работы)',
        'goods': r'(?:какой срок поставки|какой срок поставки товара|каков срок поставки товара)',
        'contract': r'(?:каков срок исполнения контракта|какой срок исполнения контракта)',
    }.items() if re.fullmatch(pattern, q)), None)
    if performance_kind:
        found = search_run_documents(run_id, DocumentSearchQuestion(query='срок исполнения'),
                                     candidate_selector=partial(delivery_candidate, object_kind=performance_kind))
        citations = found['citations']
        observations = [literal_delivery_observation(c['quote'], object_kind=performance_kind) for c in citations]
        if found['status'] == 'VERIFIED_EXCERPTS_ONLY' and observations and all(observations):
            return {**result, 'intent': 'performance_term', 'status': 'LITERAL_PERFORMANCE_OBSERVATIONS',
                    'observation': {'object_kind': performance_kind, 'mentions': observations,
                                    'distinct_literal_terms': len({o['term_literal'].casefold() for o in observations}),
                                    'effective_due_date': None},
                    'citations': citations, 'citation_kind': 'ORIGINAL_DP_CHUNK',
                    'answer': 'Явные сроки из проверенных фрагментов. Применимый срок, этапы и исключения не установлены.'}
        return {**result, 'intent': 'performance_term', 'reason': 'NO_VERIFIED_EXPLICIT_PERFORMANCE_TERM'}
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
