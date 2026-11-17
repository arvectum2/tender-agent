import hashlib
import json

import pytest
from fastapi import HTTPException

from src.modules.tender_operator_agent_demo import evidence_document_search as search
from src.modules.tender_operator_agent_demo.document_source_projection import (
    project_document_source,
)
from src.shared import document_processing as dp

RUN = 'toa-run-20261117120000-abcdef'
TEXT = 'Оплата выполненных работ производится в течение семи рабочих дней.'


@pytest.fixture
def archive(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR', str(tmp_path))
    run = tmp_path / RUN
    (run / 'input').mkdir(parents=True)
    (run / 'normalized').mkdir()
    raw = TEXT.encode()
    digest = hashlib.sha256(raw).hexdigest()
    (run / 'input/original.docx').write_bytes(raw)
    (run / 'normalized/file-01-contract_draft.txt').write_text(TEXT)
    chunk = dp.ProcessedChunk(0, TEXT, digest, 0, len(TEXT), 12, 'chunk-1')
    processed = dp.ProcessedDocument('extracted', TEXT, (chunk,), 'resource-1', 'document-1', 'tender-upload://' + digest)
    provenance, chunks = project_document_source(processed, file_id='FILE-01')
    record = {'file_id':'FILE-01','stored_name':'original.docx','data_platform_source':provenance,'evidence_chunks':chunks}
    metadata = {'run_id':RUN,'files':[record]}
    (run / 'metadata.json').write_text(json.dumps(metadata))
    calls = []
    def processor(**kwargs):
        calls.append(kwargs)
        return processed
    monkeypatch.setattr(dp, 'process_document_bytes', processor)
    return run, metadata, calls


def ask(query='оплата выполненных работ'):
    return search.search_run_documents(RUN, search.DocumentSearchQuestion(query=query))


def test_search_real_quote_verifier_with_deterministic_dp_adapter(archive):
    run, _, calls = archive
    before = {str(p):p.read_bytes() for p in run.rglob('*') if p.is_file()}
    result = ask()
    assert result['status'] == 'VERIFIED_EXCERPTS_ONLY' and len(result['citations']) == 1
    assert result['citations'][0]['quote'] == TEXT
    assert result['citations'][0]['offset_space'] == 'data_platform_chunk_text'
    assert result['verification_attempts'] == 1 and len(calls) == 1
    assert result['scope_complete'] is False and result['bid_ready'] is False
    assert {str(p):p.read_bytes() for p in run.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('change', ['original','normalized','metadata','symlink','duplicate'])
def test_invalid_candidates_never_disclose_unverified_text(archive, change):
    run, meta, _ = archive
    if change == 'original':
        (run / 'input/original.docx').write_bytes(b'changed')
    elif change == 'normalized':
        (run / 'normalized/file-01-contract_draft.txt').write_text('Оплата производится по секретному условию, отсутствующему в оригинале.')
    elif change == 'metadata':
        meta['files'][0]['evidence_chunks'][0]['text_hash'] = '0'*64
        (run / 'metadata.json').write_text(json.dumps(meta))
    elif change == 'duplicate':
        meta['files'].append(meta['files'][0])
        (run / 'metadata.json').write_text(json.dumps(meta))
    else:
        p = run / 'normalized/file-01-contract_draft.txt'
        other = run / 'outside.txt'
        other.write_text(TEXT);p.unlink();p.symlink_to(other)
    result = ask()
    assert result['status'] == 'UNKNOWN' and result['citations'] == [] and not result['scope_complete']
    assert 'секретному' not in json.dumps(result, ensure_ascii=False)


def test_no_match_and_no_other_run_fallback(archive):
    _, _, calls = archive
    assert ask('банкротство')['status'] == 'UNKNOWN'
    assert ask('как что')['reason'] == 'EXPLICIT_SEARCH_TERMS_REQUIRED'
    assert calls == []
    for run in ('../other', 'toa-run-20261117120000-123456'):
        with pytest.raises(HTTPException) as exc:
            search.search_run_documents(run, search.DocumentSearchQuestion(query='оплата'))
        assert exc.value.status_code == 404


def test_nested_unsupported_path_does_not_consume_verification_budget(archive):
    run, meta, calls = archive
    meta['files'][0]['stored_name'] = 'extracted/original.docx'
    (run / 'metadata.json').write_text(json.dumps(meta))
    result = ask()
    assert result['status'] == 'UNKNOWN' and result['verification_attempts'] == 0 and not calls
