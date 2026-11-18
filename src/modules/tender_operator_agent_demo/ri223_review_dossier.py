"""Archived RI223 operator review: bounded original evidence, not a GO engine."""
from __future__ import annotations

from pathlib import Path

from src.tender_research.rag.ri223_document_dossier import review_domains

from .evidence_document_search import (
    DocumentSearchQuestion,
    checked_search_run,
    search_run_documents,
)
from .evidence_ri223_archive import ri223_archive_observation
from .operator_stored_file_paths import checked_original_input_path
from .ri223_attachment_evidence import (
    MAX_FILE,
    MAX_REFS,
    MAX_TOTAL,
    digest,
    expected_documents,
    read_bytes,
)
from .ri223_container_evidence import (
    container_projection_scope,
    member_receipt,
    project_container,
)

_PROBES = {
    'technical_scope':'техническое задание объем услуги',
    'qualification':'участник требования квалификация лицензия',
    'application':'заявки документы состав форма',
    'evaluation':'критерий оценки',
    'contract':'договор ответственность неустойка расторжение',
    'participation':'ограничения участники субъекты малого предпринимательства',
    'schedule':'срок оказания услуг выполнения работ',
    'payment':'оплата аванс расчет платеж',
    'security':'обеспечение заявки договора гарантия',
}


def verified_inventory(run: Path, metadata: dict) -> dict:
    """Only attest stored bytes and enumerated membership, not content completeness."""
    empty={'status':'UNVERIFIED_OR_INCOMPLETE','originals_verified':0,'expected_originals':None,
           'members_verified':0,'saved_searchable_candidates':0,'opaque_containers':None,
           'archived_bytes_complete':False,'projection_complete':False}
    try:
        expected=expected_documents(run,metadata)
        records=metadata['files']
        if not isinstance(records,list) or not 1<=len(records)<=MAX_REFS or any(not isinstance(r,dict) for r in records):
            raise ValueError('Invalid inventory')
        ids=[r.get('file_id') for r in records]
        paths=[r.get('stored_name') for r in records]
        if not all(isinstance(x,str) and x for x in ids+paths) or len(set(ids))!=len(ids) or len(set(paths))!=len(paths):
            raise ValueError('Ambiguous inventory')
        notice=[r for r in records if r.get('source')=='ri223_archive']
        if len(notice)!=1 or any(r.get('source') not in {'ri223_archive','ri223_attachment','ri223_container_member'} for r in records):
            raise ValueError('Unexpected inventory role')
        parents={}
        children={}
        total=0
        for row in records:
            if row['source']=='ri223_archive':
                continue
            raw=read_bytes(checked_original_input_path(run/'input',row['stored_name']),MAX_FILE)
            sha=digest(raw)
            total+=len(raw)
            if total>MAX_TOTAL or len(raw)!=row.get('size_bytes'):
                raise ValueError('Size mismatch or budget')
            if row['source']=='ri223_attachment':
                refs=expected.get(sha)
                if (not refs or sha in parents or row.get('ri223_receipts')!=refs
                        or row.get('original_name')!=refs[0]['name'] or len(raw)!=refs[0]['bytes']
                        or row.get('extension')!=Path(refs[0]['name']).suffix.lower()
                        or Path(row['stored_name']).suffix.lower()!=row['extension']):
                    raise ValueError('Invalid attachment binding')
                parents[sha]=(row,raw)
            else:
                lineage=row['ri223_container']
                key=(lineage['parent_file_id'],lineage['member_path'])
                if key in children:
                    raise ValueError('Duplicate member binding')
                children[key]=(row,raw)
        if set(parents)!=set(expected):
            return {**empty,'expected_originals':len(expected),'reason':'ORIGINAL_SET_INCOMPLETE'}
        checked=set()
        opaque=0
        expanded=0
        for sha,(parent,raw) in parents.items():
            related={key:(row,b) for key,(row,b) in children.items() if key[0]==parent['file_id']}
            ext=parent['extension']
            if ext not in {'.rar','.zip'}:
                if related:
                    raise ValueError('Non-container parent')
                continue
            if not related:
                opaque+=1
                continue
            expanded+=1
            if expanded>1:
                raise ValueError('Only one expanded container allowed')
            members=project_container(raw,ext)
            if {key[1] for key in related}!={m.path for m in members}:
                raise ValueError('Incomplete member projection')
            for m in members:
                key=(parent['file_id'],m.path)
                row,child=related[key]
                bound={**member_receipt(sha,m,container_format=ext[1:].upper()),'parent_file_id':parent['file_id']}
                if (row['ri223_container']!=bound or child!=m.content or row.get('ri223_receipts')!=expected[sha]
                        or row.get('original_name')!=m.filename or row.get('extension')!=Path(m.filename).suffix.lower()
                        or Path(row['stored_name']).suffix.lower()!=row['extension']):
                    raise ValueError('Invalid child binding')
                checked.add(key)
        if checked!=set(children):
            raise ValueError('Unbound member')
        candidates=sum(bool(r.get('evidence_chunks')) for r in records if r['source']!='ri223_archive')
        return {'status':'VERIFIED_ARCHIVED_INVENTORY','originals_verified':len(parents),'expected_originals':len(expected),
                'members_verified':len(checked),'saved_searchable_candidates':candidates,'opaque_containers':opaque,
                'archived_bytes_complete':True,'projection_complete':opaque==0}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {**empty,'reason':'ARCHIVED_INVENTORY_UNVERIFIED'}


def build_archived_review(run_id: str, run: Path, metadata: dict, *, candidate_selector=None) -> dict:
    with container_projection_scope():
        return _build_archived_review(run_id, run, metadata, candidate_selector=candidate_selector)


def _build_archived_review(run_id: str, run: Path, metadata: dict, *, candidate_selector=None) -> dict:
    notice=ri223_archive_observation(run,metadata)
    inventory=verified_inventory(run,metadata) if notice['status']=='PINNED_RI223_ARCHIVED_NOTICE' else None
    result={'status':'UNKNOWN','notice':notice,'inventory':inventory,'domains':[],
            'scope_complete':False,'requirements_verified':False,'current_revision_attested':False,
            'lot_document_binding':'UNVERIFIED','supplier_fit':'UNKNOWN','actual_costs':'UNKNOWN',
            'contract_risk':'NOT_ASSESSED','decision':'NOT_DECIDED','go_eligible':False,
            'requires_human_review':True,'external_action_allowed':False}
    if not inventory or not inventory['archived_bytes_complete']:
        return {**result,'reason':'COMPLETE_VERIFIED_ORIGINAL_SET_REQUIRED'}
    plan=list(review_domains())
    plan.extend([('payment','Условия оплаты','contract_terms'),('security','Обеспечение заявки и договора','contract_terms')])
    for key,title,section in plan:
        question=DocumentSearchQuestion(query=_PROBES[key])
        evidence=(search_run_documents(run_id,question) if candidate_selector is None else
                  search_run_documents(run_id,question,candidate_selector=candidate_selector))
        citations=evidence['citations'] if evidence['status']=='VERIFIED_EXCERPTS_ONLY' else []
        result['domains'].append({'domain':key,'title':title,'analysis_section_id':section,
            'query':_PROBES[key],'status':'NEEDS_HUMAN_DOCUMENT_REVIEW' if citations else 'NO_CITED_DOCUMENT_EXCERPT',
            'requirements_verified':False,'supplier_fit':'UNKNOWN','lot_binding':'UNVERIFIED',
            'revision_binding':'UNVERIFIED','citations':citations})
    from .ri223_review_scoring import scoring_observation

    scoring=scoring_observation(run,metadata)
    current_run,current_metadata=checked_search_run(run_id)
    if current_run!=run or current_metadata!=metadata or verified_inventory(run,metadata)!=inventory or ri223_archive_observation(run,metadata)!=notice:
        return {**result,'domains':[],'inventory':None,'status':'UNKNOWN','reason':'SOURCE_CHANGED_DURING_REVIEW'}
    return {**result,'status':'RI223_ARCHIVED_REVIEW_ONLY',
            'scoring':scoring,
            'source_backed_domains':sum(bool(d['citations']) for d in result['domains']),
            'reason':'EVIDENCE_MATRIX_NOT_REQUIREMENTS_OR_DECISION'}
