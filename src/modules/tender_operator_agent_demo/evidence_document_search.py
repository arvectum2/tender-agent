"""Run-local lexical discovery followed by existing original-byte quote attestation."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from itertools import islice
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.modules.tender_operator_agent_demo.verified_original_quote import (
    verify_operator_run_quote,
)

_MAX_FILES = 24
_MAX_TEXT_BYTES = 1024 * 1024
_MAX_CHECKS = 2
_STOP = frozenset({'какой','какая','какие','каково','каков','сколько','есть','нужно','найди','покажи','где','что','как','при','для','или','the','what','where','which','how','are','and','does','about'})
_FILE = re.compile(r'FILE-[0-9]{2,4}\Z')
_RUN = re.compile(r'toa-run-[0-9]{14}-[a-f0-9]{6}\Z')


class DocumentSearchQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=3, max_length=240)


def _terms(query: str) -> set[str]:
    return set(re.findall(r'[^\W_]{3,}', query.casefold())) - _STOP


def _candidate(text: str, terms: set[str]) -> tuple[int, str] | None:
    """Exact whole words, bounded quote windows; candidates are NOT evidence."""
    best = None
    for i, line in enumerate(text.splitlines()):
        if i >= 20000:
            break
        line = line.strip()
        if len(line) < 20:
            continue
        matches = (m for m in re.finditer(r'[^\W_]{3,}', line) if m.group().casefold() in terms)
        for match in islice(matches, 24):
            start = max(0, match.start() - 60)
            end = min(len(line), match.end() + 100)
            excerpt = line[start:end].strip()
            score = len(_terms(excerpt) & terms)
            if len(excerpt) >= 20 and score and (best is None or score > best[0]):
                best = (score, excerpt)
        if best and best[0] == len(terms):
            break
    return best


def _bounded_text(root: Path, file_id: str) -> str | None:
    if root.is_symlink() or not root.is_dir():
        return None
    try:
        matches = list(root.glob(file_id.lower() + '-*.txt'))
        if len(matches) != 1:
            return None
        path = matches[0]
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root.resolve():
            return None
        with path.open('rb') as f:
            raw = f.read(_MAX_TEXT_BYTES + 1)
        if len(raw) > _MAX_TEXT_BYTES:
            return None
        return raw.decode('utf-8')
    except (OSError, UnicodeError):
        return None


def checked_search_run(run_id: str) -> tuple[Path, dict[str, Any]]:
    from src.modules.tender_operator_agent_demo.upload_service_legacy import (
        get_demo_runs_root,
        load_demo_run_metadata,
    )

    if not _RUN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail='Run not found')
    base = get_demo_runs_root().resolve()
    run = base / run_id
    if run.is_symlink() or not run.is_dir() or (run / 'metadata.json').is_symlink():
        raise HTTPException(status_code=404, detail='Run not found')
    metadata = load_demo_run_metadata(run_id)
    if metadata.get('run_id') != run_id or (run / 'input').is_symlink():
        raise HTTPException(status_code=404, detail='Run not found')
    return run, metadata


def search_run_documents(run_id: str, request: DocumentSearchQuestion, *, candidate_selector: Callable[[str, set[str]], tuple[int, str] | None] = _candidate, record_candidate_selector: Callable[[str, set[str], dict], tuple[int, str] | None] | None = None) -> dict[str, Any]:
    run, metadata = checked_search_run(run_id)
    result = {'contract': 'apr08_run_lexical_evidence_v1', 'run_id': run_id,
              'status': 'UNKNOWN', 'citations': [], 'files_examined': 0, 'verification_attempts': 0,
              'scope_complete': False, 'semantic_answer_verified': False, 'current_revision_attested': False,
              'legal_requirement_attested': False, 'bid_ready': False, 'requires_human_review': True,
              'external_action_allowed': False}
    terms = _terms(request.query)
    if not terms or len(terms) > 16:
        return {**result, 'reason': 'EXPLICIT_SEARCH_TERMS_REQUIRED'}
    records = metadata.get('files')
    if not isinstance(records, list):
        return {**result, 'reason': 'NO_SAVED_SOURCE_INDEX'}
    ids = Counter(r.get('file_id') for r in records if isinstance(r, dict) and isinstance(r.get('file_id'), str))
    candidates = []
    for record in records[:_MAX_FILES]:
        if not isinstance(record, dict):
            continue
        fid = record.get('file_id')
        source = record.get('data_platform_source')
        stored = record.get('stored_name')
        if (not isinstance(fid, str) or not _FILE.fullmatch(fid) or ids[fid] != 1
                or not isinstance(stored, str) or not stored or Path(stored).name != stored
                or '/' in stored or '\\' in stored or stored in {'.', '..'}
                or not isinstance(source, dict) or source.get('extraction_status') != 'extracted'
                or not record.get('evidence_chunks')):
            continue
        text = _bounded_text(run / 'normalized', fid)
        if text is None:
            continue
        result['files_examined'] += 1
        candidate = (candidate_selector(text, terms) if record_candidate_selector is None else
                     record_candidate_selector(text, terms, record))
        if candidate:
            candidates.append((candidate[0], fid, candidate[1], source.get('canonical_uri')))
    for _, fid, quote, uri in sorted(candidates, key=lambda c: (-c[0], c[1]))[:_MAX_CHECKS]:
        result['verification_attempts'] += 1
        try:
            checked = verify_operator_run_quote(run_id=run_id, file_id=fid, exact_quote=quote)
        except (HTTPException, OSError, ValueError):
            continue
        evidence = checked.get('evidence')
        if (checked.get('status') != 'literal_quote_found_in_extracted_original_only' or not isinstance(evidence, dict)
                or evidence.get('file_id') != fid or evidence.get('quote') != quote
                or not re.fullmatch(r'[a-f0-9]{64}', str(evidence.get('original_sha256') or ''))
                or uri != 'tender-upload://' + evidence['original_sha256']
                or not evidence.get('chunk_id') or evidence.get('offset_space') != 'data_platform_chunk_text'
                or type(evidence.get('quote_char_start_in_chunk')) is not int
                or type(evidence.get('quote_char_end_in_chunk')) is not int
                or evidence['quote_char_start_in_chunk'] < 0
                or evidence['quote_char_end_in_chunk'] - evidence['quote_char_start_in_chunk'] != len(quote)):
            continue
        cite = {k: evidence[k] for k in ('file_id','chunk_id','quote','original_sha256',
                                    'quote_char_start_in_chunk','quote_char_end_in_chunk','offset_space')}
        if 'ri223_container' in evidence:
            cite['ri223_container'] = evidence['ri223_container']
        result['citations'].append(cite)
    if not result['citations']:
        return {**result, 'reason': 'NO_VERIFIED_MATCH_IN_BOUNDED_SEARCH'}
    return {**result, 'status': 'VERIFIED_EXCERPTS_ONLY', 'reason': 'LEXICAL_MATCH_NOT_SEMANTIC_ANSWER'}
