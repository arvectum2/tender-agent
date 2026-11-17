"""Receipt-bound local originals; no network acquisition or archive expansion."""
from __future__ import annotations

import hashlib
import mimetypes
import re
from collections import Counter
from pathlib import Path

from src.tender_research.providers.ri223_soap_evidence import (
    MAX_ARCHIVE_BYTES,
    parse_ri223_archive,
)
from src.tender_research.rag.presets import tender_processing_collection_id

from .document_source_projection import project_document_source
from .evidence_ri223_archive import SOURCE, ri223_archive_observation
from .operator_document_extraction import extract_operator_document
from .operator_stored_file_paths import checked_original_input_path
from .ri223_container_evidence import PROCESSABLE_MEMBERS, member_receipt, project_rar
from .ri223_receipt_catalog import configured_receipts

MAX_FILE = 12 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
MAX_REFS = 24
PROCESSABLE = {'.pdf', '.docx', '.doc'}
ALLOWED = PROCESSABLE | {'.rar', '.zip'}


def read_bytes(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Unsafe original')
    with path.open('rb') as f:
        data = f.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError('Original size outside budget')
    return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reference_key(doc: dict) -> tuple:
    return doc['name'], doc['source_kind'], doc['xml_sha256']


def expected_documents(run: Path, metadata: dict) -> dict[str, list[dict]]:
    """Authenticate source receipts independently of the run."""
    receipts = configured_receipts()
    number = metadata.get('procurement_id')
    if metadata.get('procurement_source') != SOURCE or not receipts or number not in receipts:
        raise ValueError('Explicit trusted attachment receipt required')
    receipt = receipts[number]
    docs = receipt.get('documents')
    if receipt.get('archived_attachment_reference_coverage_complete') is not True or not isinstance(docs, list) or not 0 < len(docs) <= MAX_REFS:
        raise ValueError('Complete archived binary receipt required')
    if ri223_archive_observation(run, metadata)['status'] != 'PINNED_RI223_ARCHIVED_NOTICE':
        raise ValueError('Archived notice not verified')
    archive = checked_original_input_path(run/'input',metadata.get('archive_stored_name'))
    if digest(read_bytes(archive, MAX_ARCHIVE_BYTES)) != receipt['archive_sha256']:
        raise ValueError('Archive changed')
    parsed = parse_ri223_archive(archive,number)
    refs = Counter((d.file_name,d.raw_meta['source_document_kind'],d.raw_meta['evidence']['xml_sha256']) for d in parsed.documents)
    grouped: dict[str, list[dict]] = {}
    for d in docs:
        if not isinstance(d,dict):
            raise TypeError('Invalid document receipt')
        name,kind,xml=reference_key(d)
        sha,size=d['sha256'],d['bytes']
        if (not isinstance(name,str) or not 0<len(name)<=260 or any(c in name for c in ('/','\\')) or any(ord(c)<32 for c in name)
                or Path(name).suffix.lower() not in ALLOWED or kind not in ('purchaseNotice','purchaseProtocol','explanation')
                or not isinstance(xml,str) or not re.fullmatch(r'[a-f0-9]{64}',xml)
                or not isinstance(sha,str) or not re.fullmatch(r'[a-f0-9]{64}',sha)
                or type(size) is not int or not 0<size<=MAX_FILE):
            raise ValueError('Unverifiable document receipt')
        grouped.setdefault(sha,[]).append({k:d[k] for k in ('name','source_kind','xml_sha256','sha256','bytes')})
    # Names with the same XML/kind must uniquely identify a reference. The
    # legacy receipt does not carry URL/UID, so ambiguous duplicate keys fail.
    if any(count != 1 for count in refs.values()) or Counter(reference_key(d) for d in docs)!=refs:
        raise ValueError('Reference inventory mismatch')
    if any(len({(d['name'],d['bytes']) for d in group})!=1 for group in grouped.values()):
        raise ValueError('Ambiguous identical binary metadata')
    if sum(group[0]['bytes'] for group in grouped.values())>MAX_TOTAL:
        raise ValueError('Aggregate size outside budget')
    if digest(read_bytes(archive, MAX_ARCHIVE_BYTES)) != receipt['archive_sha256']:
        raise ValueError('Archive changed during verification')
    return grouped


def _store_file(stage,metadata,name,content,refs,processor,*,source,lineage=None):
    sha=digest(content)
    ext=Path(name).suffix.lower()
    fid=f'FILE-{len(metadata["files"])+1:02d}'
    stored=f'{fid.lower()}-{sha[:16]}{ext}'

    (stage/'input'/stored).write_bytes(content)
    row={'file_id':fid,'original_name':name,'display_name':name,'stored_name':stored,'extension':ext,
         'size_bytes':len(content),'content_type':mimetypes.guess_type(name)[0] or 'application/octet-stream',
         'extracted_text_available':False,'source':source,'ri223_receipts':refs,'extraction_status':'unsupported','warnings':[]}
    if ext in (PROCESSABLE_MEMBERS if lineage else PROCESSABLE):
        text,_,status,processed=extract_operator_document(file_name=stored,content=content,
            collection_id=tender_processing_collection_id('upload'),processor=processor)
        row['extraction_status']=status
        if processed and status=='extracted' and text and processed.canonical_uri=='tender-upload://'+sha:
            provenance,chunks=project_document_source(processed,file_id=fid)
            if chunks and len(text.encode('utf-8'))<=1024*1024:
                row.update(data_platform_source=provenance,evidence_chunks=chunks,extracted_text_available=True)
                (stage/'normalized'/(fid.lower()+'-original.txt')).write_text(text,encoding='utf-8')
            else:
                row['extraction_status']='unverified'
        elif status=='extracted':
            row['extraction_status']='unverified'
    if not row['extracted_text_available']:
        row['warnings'].append('Текст не подтверждён: '+row['extraction_status'])
    if lineage:
        row['ri223_container']=lineage
    metadata['files'].append(row)
    return row


def import_attachments(stage: Path, metadata: dict, paths: list[Path], processor, *, expand_rar: bool = False) -> None:
    expected=expected_documents(stage,metadata)
    if len(paths)!=len(expected):
        raise ValueError('Provide one original per unique receipt digest')
    blobs={}
    for path in paths:
        data=read_bytes(path, MAX_FILE)
        sha=digest(data)
        if sha in blobs or sha not in expected or len(data)!=expected[sha][0]['bytes']:
            raise ValueError('Unexpected, duplicated or changed attachment')
        blobs[sha]=data
    if set(blobs)!=set(expected):
        raise ValueError('Incomplete attachment set')

    # Validate every container before processing or publishing any file.
    containers = [sha for sha,refs in expected.items() if expand_rar and Path(refs[0]['name']).suffix.lower() == '.rar']
    if len(containers)>1:
        raise ValueError('Only one RAR container per evidence run')
    projections = {sha: project_rar(blobs[sha]) for sha in containers}
    if expand_rar and 1 + len(expected) + sum(map(len,projections.values())) > MAX_REFS:
        raise ValueError('Workspace document count exceeds search budget')
    if sum(len(b) for b in blobs.values()) + sum(len(m.content) for ms in projections.values() for m in ms) > MAX_TOTAL:
        raise ValueError('Expanded attachment budget exceeded')
    normal=stage/'normalized'
    normal.mkdir(mode=0o700)
    for sha,refs in expected.items():
        parent=_store_file(stage,metadata,refs[0]['name'],blobs[sha],refs,processor,source='ri223_attachment')
        for member in projections.get(sha,()):
            lineage=member_receipt(sha,member)
            _store_file(stage,metadata,member.filename,member.content,refs,processor,
                        source='ri223_container_member',
                        lineage={**lineage,'parent_file_id':parent['file_id']})
    metadata['attachments_status']='verified_archived_originals'
    metadata['limitations']=['Архивные оригиналы проверены; извлечение может быть неполным. Полный анализ недоступен.']
    metadata['ri223_attachment_extraction']={'unique_originals':len(expected),'references':sum(map(len,expected.values())),
        'searchable':sum(bool(r.get('evidence_chunks')) for r in metadata['files']),
        'container_members':sum(map(len,projections.values())),
        'current_revision_attested':False,'full_analysis_allowed':False}


def attachment_quote_allowed(run: Path, metadata: dict, row: dict) -> bool:
    """Recheck independent receipt and original bytes before a quote."""
    try:
        if row.get('source')!='ri223_attachment' or row.get('extension') not in PROCESSABLE:
            return False
        ids=[item.get('file_id') for item in metadata['files'] if isinstance(item,dict)]
        if ids.count(row.get('file_id'))!=1:
            return False
        expected=expected_documents(run,metadata)
        file=checked_original_input_path(run/'input',row.get('stored_name'))
        raw=read_bytes(file,MAX_FILE)
        sha=digest(raw)
        refs=expected.get(sha)
        return bool(refs and row.get('ri223_receipts')==refs and row.get('original_name')==refs[0]['name']
            and row.get('size_bytes')==len(raw)==refs[0]['bytes']
            and row.get('extension')==Path(refs[0]['name']).suffix.lower()
            and row.get('data_platform_source',{}).get('canonical_uri')=='tender-upload://'+sha)
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return False


def verified_container_lineage(run: Path, metadata: dict, row: dict) -> dict | None:
    """Re-derive a child from the independently receipt-bound parent at quote time."""
    try:
        if row.get('source') != 'ri223_container_member':
            return None
        lineage = row['ri223_container']
        records = [r for r in metadata['files'] if isinstance(r,dict)]
        if sum(r.get('file_id') == row.get('file_id') for r in records) != 1:
            return None
        parents = [r for r in records if r.get('file_id') == lineage['parent_file_id']]
        if len(parents) != 1:
            return None
        parent = parents[0]
        expected = expected_documents(run,metadata)
        if parent.get('source') != 'ri223_attachment' or parent.get('extension') != '.rar':
            return None
        parent_bytes = read_bytes(checked_original_input_path(run/'input',parent.get('stored_name')),MAX_FILE)
        sha = digest(parent_bytes)
        refs = expected.get(sha)
        if (not refs or parent.get('ri223_receipts') != refs or row.get('ri223_receipts') != refs
                or parent.get('original_name') != refs[0]['name']
                or Path(refs[0]['name']).suffix.lower() != '.rar'
                or parent.get('size_bytes') != len(parent_bytes)
                or len(parent_bytes) != refs[0]['bytes']
                or sha != lineage['parent_sha256']):
            return None
        child = read_bytes(checked_original_input_path(run/'input',row.get('stored_name')),MAX_FILE)
        child_sha = digest(child)
        if (row.get('size_bytes') != len(child) or child_sha != lineage['member_sha256']
                or row.get('data_platform_source',{}).get('canonical_uri') != 'tender-upload://'+child_sha):
            return None
        members = [m for m in project_rar(parent_bytes) if m.path == lineage['member_path']]
        if len(members) != 1:
            return None
        m = members[0]
        bound = {**member_receipt(sha,m),'parent_file_id':parent['file_id']}
        if (bound != lineage or child != m.content or row.get('original_name') != m.filename
                or row.get('extension') != Path(m.filename).suffix.lower()
                or Path(row['stored_name']).suffix.lower() != row['extension']):
            return None
        return {**bound,'parent_name':parent['original_name'],'source_references':refs}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
