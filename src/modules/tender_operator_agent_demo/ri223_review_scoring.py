"""Exact historical scoring receipt, never a supplier verdict or generic parser."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.modules.company_profile_store.qualification_223_observer import (
    observe_verified_pdf_layout,
    verify_ri223_originals,
)

from .operator_stored_file_paths import checked_original_input_path
from .ri223_attachment_evidence import digest, read_bytes, verified_container_lineage

_RECEIPT = Path(__file__).resolve().parents[3] / 'docs/acceptance/ri223_32616445795_original_scoring_receipt_2026-10-13.json'
_RECEIPT_SHA = 'b5f2591cf4ef5a452330e00ba3e66c09997fae0ea2bed41a1d6633283a306d0c'
_MAX = 8*1024*1024


def scoring_observation(run: Path, metadata: dict) -> dict:
    unknown={'status':'UNKNOWN','competitive_recommendation':'NOT_ASSESSED'}
    if metadata.get('procurement_id')!='32616445795':
        return unknown
    try:
        receipt_raw=read_bytes(_RECEIPT,32*1024)
        if digest(receipt_raw)!=_RECEIPT_SHA:
            return unknown
        receipt=json.loads(receipt_raw)
        records=metadata['files']
        matches=[r for r in records if r.get('source')=='ri223_container_member'
                 and r.get('ri223_container',{}).get('member_path')==receipt['evaluation_pdf_member']]
        if len(matches)!=1:
            return unknown
        row=matches[0]
        lineage=verified_container_lineage(run,metadata,row)
        if not lineage or lineage['member_sha256']!=receipt['evaluation_pdf_sha256']:
            return unknown
        parents=[r for r in records if r.get('file_id')==lineage['parent_file_id']]
        if len(parents)!=1:
            return unknown
        def original(name):
            return read_bytes(checked_original_input_path(run/'input',name),_MAX)
        soap=original(metadata['archive_stored_name'])
        rar=original(parents[0]['stored_name'])
        pdf=original(row['stored_name'])
        trusted=verify_ri223_originals(soap,rar,pdf,receipt)
        scoring=observe_verified_pdf_layout(pdf)
        return {**trusted,**scoring,'status':'PINNED_SCORING_OBSERVATION_ONLY','source_lineage':lineage,
                'file_id':row['file_id'],'digital_signature_verified':False}
    except (OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError):
        return unknown
