"""Bind a historical DOCX candidate to the existing independently pinned source."""
from __future__ import annotations

from src.modules.company_profile_store.application_checklist import _rows
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    ri223_archive_observation,
)
from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)
from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import read_bytes
from src.modules.tender_operator_agent_demo.ri223_container_evidence import (
    container_projection_scope,
)
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    verified_inventory,
)

from .checklist_bundle_gate import _derive, observe_application
from .original_form_candidate import MAX_BYTES, _sha


def observe_original_form(run_id, customer_id, item_code, file_id, signatory, goods_used):
    run, meta = checked_search_run(run_id)
    with container_projection_scope():
        inventory = verified_inventory(run, meta)
        notice = ri223_archive_observation(run, meta)
        packet = observe_application(run_id)
        plan, scope, plan_sha = _derive(packet, customer_id=customer_id, run_id=run_id,
                                       signatory=signatory, goods_used=goods_used)
        item = next((x for x in plan.items if x.code == item_code), None)
        if (not inventory['archived_bytes_complete'] or not inventory['projection_complete']
                or notice['status'] != 'PINNED_RI223_ARCHIVED_NOTICE' or not notice.get('observed_version')
                or meta.get('procurement_id') != plan.procurement_ref
                or not item or item.role != 'FORM' or item.applicability != 'REQUIRED'):
            raise ValueError('Verified archived applicable form required')
        row = next(x for x in _rows(packet, signatory, goods_used) if x['code'] == item_code)
        pairs = {(f['file_id'], f['original_sha256']) for fs in row['source'].values() for f in fs}
        records = [r for r in meta['files'] if r.get('file_id') == file_id]
        if len(records) != 1:
            raise ValueError('Ambiguous source member')
        record = records[0]
        if record.get('source') not in ('ri223_attachment', 'ri223_container_member') or record.get('extension') != '.docx':
            raise ValueError('Original DOCX member required')
        raw = read_bytes(checked_original_input_path(run/'input', record['stored_name']), MAX_BYTES)
        hashes = {(c['archive_sha256'], c['source_sha256']) for c in notice['citations']}
        if len(hashes) != 1 or pairs != {(file_id, _sha(raw))}:
            raise ValueError('Form not the exact requirement source member')
        archive_sha, xml_sha = next(iter(hashes))
        if not any(r.get('source_kind') == 'purchaseNotice' and r.get('xml_sha256') == xml_sha
                   for r in record.get('ri223_receipts', [])):
            raise ValueError('Member not bound to observed notice revision')
        if (checked_search_run(run_id) != (run, meta) or verified_inventory(run, meta) != inventory
                or ri223_archive_observation(run, meta) != notice):
            raise ValueError('Archived source changed during review')
    return raw, {'customer_id': customer_id, 'run_id': run_id, 'procurement_ref': plan.procurement_ref,
                 'item_code': item_code, 'file_id': file_id, 'template_sha256': _sha(raw),
                 'archive_sha256': archive_sha, 'notice_xml_sha256': xml_sha,
                 'observed_version': notice['observed_version'], 'plan_sha256': plan_sha,
                 'requirement_sha256': scope['requirements'][item_code]['source_sha256']}
