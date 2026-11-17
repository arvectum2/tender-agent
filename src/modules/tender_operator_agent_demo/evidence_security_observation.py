"""Read explicit security fields from the already verified archived EIS revision."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.modules.tender_operator_agent_demo import operator_workspace_evidence as source

_GROUPS = {'bid_security': 'applicationGuarantee', 'contract_security': 'contractGuarantee'}


def archived_security_observation(run_id: str, kind: str, *, include_procedure: bool = False) -> dict[str, Any]:
    result = {'status': 'UNKNOWN', 'kind': kind, 'amount': None, 'percent': None,
              'currency': None, 'calculated_amount': None, 'actual_requirement_attested': False,
              'citations': [], 'reason': 'PINNED_ARCHIVE_REQUIRED'}
    group_tag = _GROUPS[kind]
    metadata = source.load_demo_run_metadata(run_id)
    if metadata.get('procurement_source') != 'zakupki_gov_ru_getdocs_ip':
        return result
    pinned = source._pinned_archived_notice_revision(run_id, metadata, source._matching_notice_xml_candidates(run_id, metadata))
    if pinned is None:
        return result
    xml, item, version = pinned
    notice_type = metadata['official_eis_procedure'].get('notice_type')
    if notice_type not in ('epNotificationEF2020', 'epNotificationEOK2020', 'epNotificationEZK2020') or source._tag(xml) != 'export':
        return result
    scope = ('export', notice_type, 'notificationInfo', 'customerRequirementsInfo', 'customerRequirementInfo')
    parent = xml
    for tag in scope[1:]:
        nodes = [e for e in parent if source._tag(e) == tag]
        if len(nodes) != 1:
            return {**result, 'reason': 'CUSTOMER_SCOPE_NOT_UNIQUE'}
        parent = nodes[0]
    if sum(source._tag(e) == 'customerRequirementInfo' for e in xml.iter()) != 1:
        return {**result, 'reason': 'CUSTOMER_SCOPE_NOT_UNIQUE'}
    groups = [e for e in parent if source._tag(e) == group_tag]
    if len(groups) != 1 or sum(source._tag(e) == group_tag for e in xml.iter()) != 1:
        return {**result, 'reason': 'SECURITY_GROUP_NOT_UNIQUE_OR_MISSING'}
    file_id = str(item.get('file_id') or '')
    document = Path(str(item.get('original_name') or '')).name
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', file_id) or not document:
        return result
    if include_procedure:
        values = [e for e in groups[0] if source._tag(e) == 'procedureInfo']
        if len(values) != 1 or list(values[0]):
            return {**result, 'reason': 'PROCEDURE_TEXT_NOT_UNIQUE_OR_MISSING'}
        raw = (values[0].text or '').strip()
        if not 20 <= len(raw) <= 12000 or any(ord(c) < 32 and c not in '\r\n\t' for c in raw):
            return {**result, 'reason': 'PROCEDURE_TEXT_UNSUPPORTED'}
        path = '/'.join((*scope, group_tag, 'procedureInfo'))
        return {**result, 'status': 'ARCHIVED_SECURITY_PROCEDURE', 'archived_version': version,
                'citations': [{'file_id': file_id, 'document': document, 'source_ref': 'eis-xml:' + file_id + ':' + path,
                               'locator': 'XML:' + path, 'excerpt': raw}], 'reason': 'EXPLICIT_CUSTOMER_PROCEDURE_ONLY'}
    for field, tag in [('amount', 'amount'), ('percent', 'part')]:
        values = [e for e in groups[0] if source._tag(e) == tag]
        if len(values) != 1 or list(values[0]):
            continue
        raw = (values[0].text or '').strip()
        if not re.fullmatch(r'[0-9]{1,18}(?:\.[0-9]{1,4})?', raw):
            continue
        if field == 'percent' and Decimal(raw) > 100:
            continue
        path = '/'.join((*scope, group_tag, tag))
        result[field] = raw
        result['citations'].append({'file_id': file_id, 'document': document, 'source_ref': 'eis-xml:' + file_id + ':' + path,
                                    'locator': 'XML:' + path, 'excerpt': raw})
    if not result['citations']:
        return {**result, 'reason': 'NO_UNIQUE_EXPLICIT_VALUES'}
    return {**result, 'status': 'ARCHIVED_SECURITY_FIELDS', 'archived_version': version,
            'reason': 'EXPLICIT_XML_FIELDS_ONLY'}
