"""Separate legal references quoted by a customer from verified legal texts."""
from __future__ import annotations

import re
from typing import Any

from src.modules.tender_operator_agent_demo.evidence_security_observation import (
    archived_security_observation,
)

# Extract only explicit nearby article + act pairs, not unrelated numbers from the clause.
_ARTICLE = re.compile(r'\b(?:стать(?:я|и|е|ю|ей)|ст\.)\s*([0-9]{1,3}(?:\.[0-9]{1,2})?)\s+(?:(?:федерального\s+)?закона\s+)?(?:№\s*)?(44|223)\s*[-‑–]\s*фз\b', re.IGNORECASE)
_DECREE = re.compile(r'\bпостановлени(?:е|я|ем|ю|и)\s+правительства\s+(?:рф|российской федерации)\s+от\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})\s*№\s*([0-9]{1,5})\b', re.IGNORECASE)


def extract_customer_legal_references(text: str) -> list[dict[str, Any]]:
    references = []
    seen = set()
    for match, kind in sorted([(m, 'FEDERAL_LAW_ARTICLE') for m in _ARTICLE.finditer(text)] +
                              [(m, 'GOVERNMENT_DECREE') for m in _DECREE.finditer(text)], key=lambda v: v[0].start()):
        key = (kind, *match.groups())
        if key in seen:
            continue
        seen.add(key)
        reference = {'kind': kind, 'literal': match[0], 'char_start_in_excerpt': match.start(),
                     'char_end_in_excerpt': match.end(), 'statute_text_verified': False,
                     'applicability_verified': False}
        if kind == 'FEDERAL_LAW_ARTICLE':
            reference.update(article=match[1], act=match[2]+'-ФЗ')
        else:
            reference.update(act='Постановление Правительства РФ', stated_date=match[1], stated_number=match[2])
        references.append(reference)
        if len(references) == 20:
            break
    return references


def legal_reference_observation(run_id: str, kind: str) -> dict[str, Any]:
    source = archived_security_observation(run_id, kind, include_procedure=True)
    if source['status'] != 'ARCHIVED_SECURITY_PROCEDURE':
        return {'status': 'UNKNOWN', 'reason': source['reason'], 'citations': []}
    cite = source['citations'][0]
    return {'status': 'CUSTOMER_TERMS_LEGAL_REFERENCES', 'kind': kind, 'citations': [cite],
            'customer_text_verified': True, 'statute_text_verified': False, 'current_law_verified': False,
            'legal_conclusion': None, 'references_complete': False,
            'references': extract_customer_legal_references(cite['excerpt']),
            'review_questions': [
                'Сверить названные нормы с официальной редакцией на юридически значимую дату.',
                'Проверить условия, исключения и применимость к конкретному участнику и закупке.',
                'Уточнить форму, сумму, базу расчёта и срок обеспечения по полному комплекту документации.',
            ]}
