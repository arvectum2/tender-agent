"""Bounded full-paragraph attestation for explicitly reviewed archived sources."""
from __future__ import annotations

from functools import cache

from .evidence_clause_search import _saved_chunks
from .evidence_document_search import _bounded_text, checked_search_run
from .ri223_attachment_evidence import (
    attachment_quote_allowed,
    verified_container_lineage,
)
from .ri223_container_evidence import container_projection_scope
from .ri223_linked_contract import _SOURCE_SHA
from .ri223_review_dossier import verified_inventory
from .ri223_staged_source import SOURCE_PARAGRAPHS
from .verified_original_quote import verify_operator_run_quote

DRAFT_SHA, NOTICE_SHA = [sha for sha in SOURCE_PARAGRAPHS if sha != _SOURCE_SHA]


def partition_paragraph(quote, chunks):
    """Choose a full, bounded word partition; never splice unrelated text."""
    if not 20 <= len(quote) <= 1800 or len(chunks) > 4096:
        return None
    words=quote.split(' ')
    if len(words)>300:
        return None

    @cache
    def find(i, remaining):
        if i==len(words):
            return ()
        if not remaining:
            return None
        for j in range(len(words),i,-1):
            part=' '.join(words[i:j])
            if len(part)<20 or sum(c.count(part)==1 for c in chunks)!=1:
                continue
            tail=find(j,remaining-1)
            if tail is not None:
                return (part,*tail)
        return None

    result=find(0,6)
    return result if result and ' '.join(result)==quote else None


def _attest(run_id,run,meta,sha,*,verifier):
    rows=[x for x in meta.get('files',[]) if x.get('data_platform_source',{}).get('canonical_uri')=='tender-upload://'+sha]
    if len(rows)!=1:
        return {}
    row=rows[0]
    lineage=None
    if row.get('source')=='ri223_container_member':
        lineage=verified_container_lineage(run,meta,row)
        allowed=bool(lineage and lineage['member_sha256']==sha)
    else:
        allowed=attachment_quote_allowed(run,meta,row)
    if not allowed:
        return {}
    text=_bounded_text(run/'normalized',row['file_id'])
    chunks=_saved_chunks(text,row) if text else None
    if not chunks:
        return {}
    verified={}
    for label,quote in SOURCE_PARAGRAPHS[sha].items():
        parts=partition_paragraph(quote,chunks)
        if not parts:
            continue
        fragments=[]
        for q in parts:
            packet=verifier(run_id=run_id,file_id=row['file_id'],exact_quote=q)
            ev=packet.get('evidence')
            if not (packet.get('status')=='literal_quote_found_in_extracted_original_only'
                    and isinstance(ev,dict) and ev.get('original_sha256')==sha
                    and ev.get('file_id')==row['file_id'] and ev.get('quote')==q
                    and ev.get('chunk_id') and ev.get('ri223_container')==lineage):
                break
            fragments.append(ev)
        if ' '.join(x['quote'] for x in fragments)==quote:
            verified[label]=fragments
    return verified


def observe_staged_terms(run_id, *, verifier=verify_operator_run_quote):
    run,meta=checked_search_run(run_id)
    number=meta.get('procurement_id')
    if number=='32616445632':
        shas=(DRAFT_SHA,NOTICE_SHA)
    elif number=='32616445795':
        shas=(_SOURCE_SHA,)
    else:
        return {'status':'UNKNOWN','reason':'UNREVIEWED_SOURCE'}
    with container_projection_scope():
        inventory=verified_inventory(run,meta)
        if not inventory['archived_bytes_complete'] or not inventory['projection_complete']:
            return {'status':'UNKNOWN','reason':'COMPLETE_ARCHIVED_ORIGINALS_REQUIRED'}
        docs={sha:_attest(run_id,run,meta,sha,verifier=verifier) for sha in shas}
        current,current_meta=checked_search_run(run_id)
        if current!=run or current_meta!=meta or verified_inventory(run,meta)!=inventory:
            return {'status':'UNKNOWN','reason':'SOURCE_CHANGED_DURING_REVIEW'}
    complete=all(set(docs[sha])==set(SOURCE_PARAGRAPHS[sha]) for sha in shas)
    return {'status':'VERIFIED_REVIEWED_PAYMENT_TERMS_ONLY' if complete else 'INCOMPLETE',
            'procurement_id':number,'source_groups':docs,'complete_reviewed_groups':complete,
            'source_precedence_resolved':False,'whole_contract_complete':False,
            'current_revision_attested':False,'go_eligible':False}
