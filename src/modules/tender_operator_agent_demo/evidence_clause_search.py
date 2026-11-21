"""Experimental cue-based ranking of whole literal lines, not semantic evidence."""
from __future__ import annotations

import hashlib
import re
from heapq import nlargest
from itertools import islice

from .evidence_document_search import _candidate

_EVALUATION = frozenset({'критерий','оценки'})
_CONTRACT = frozenset({'договор','ответственность','неустойка','расторжение'})
_NUMBER = re.compile(r'^\s*\d{1,2}(?:\.\d{1,2}){1,5}\.?(?:\s+|$)')
_CRITERIA = re.compile(r'\bкритери[а-яё]*\b')
_ASSESS_BIDS = re.compile(r'\b(?:оценк[а-яё]*|сопоставлени[а-яё]*|ранжировани[а-яё]*)\s+(?:(?:поданных|поступивших|ценовых)\s+)?(?:заяв[а-яё]*|предложени[а-яё]*)\b')
_WINNER = re.compile(r'\b(?:победител[а-яё]*|первый номер)\b')
_RANK_RULE = re.compile(r'\b(?:наименьш[а-яё]*|минимальн[а-яё]*|наибольш[а-яё]*|максимальн[а-яё]*|лучш[а-яё]*|присваива[а-яё]*|балл[а-яё]*|значимост[а-яё]*)\b')
_TERM = re.compile(r'\b(?:неустойк[а-яё]*|штраф[а-яё]*|пен[яиейю]+|ответственност[а-яё]*|расторжени[а-яё]*|отказ[а-яё]*|оплат[а-яё]*|возмещ[а-яё]*|убытк[а-яё]*|обязательств[а-яё]*)\b')
_ACTION = re.compile(r'\b(?:обязан[а-яё]*|обязует[а-яё]*|вправе|должен|должна|должны|подлеж[а-яё]*|взыскива[а-яё]*|уплачива[а-яё]*|возмеща[а-яё]*|производит[а-яё]*|осуществля[а-яё]*|нес[её]т|расторга[а-яё]*|отказаться|не допускается)\b')
_VALUE = re.compile(r'\d+(?:[.,]\d+)?\s*%|\b\d+\s*(?:рабочих|календарных)\s+дней\b')
_REFERRAL = re.compile(r'^(?:[\d.]+\s+)?(?:в соответствии с условиями договора|согласно положению о закупке)\.?$',re.IGNORECASE)


def clause_candidate(text: str, terms: set[str]) -> tuple[int, str] | None:
    """For two fixed probes, prefer complete bounded lines with explicit cues.

    Other queries use exactly the prior selector. A match is only a candidate;
    no clause scope, applicability, exceptions or legal result is inferred.
    """
    if terms not in (_EVALUATION,_CONTRACT):
        return _candidate(text,terms)
    return max(_clause_candidates(text,terms),key=lambda x:x[0],default=None)


def _clause_candidates(text,terms):
    for line in islice(text.splitlines(),20000):
        quote = line.strip()
        if not 20 <= len(quote) <= 800 or any(ord(c)<32 for c in quote):
            continue
        normalized = quote.casefold().replace('ё','е')
        if _REFERRAL.fullmatch(normalized):
            continue
        if terms == _EVALUATION:
            criteria = bool(_CRITERIA.search(normalized) and _ASSESS_BIDS.search(normalized))
            rule = bool(_WINNER.search(normalized) and _RANK_RULE.search(normalized))
            if not (criteria or rule):
                continue
            score = 4*int(criteria)+4*int(rule)+2*int(bool(_RANK_RULE.search(normalized)))
        else:
            if not (_TERM.search(normalized) and _ACTION.search(normalized)):
                continue
            score = 4+2*int(bool(_VALUE.search(normalized)))
        score += int(bool(_NUMBER.match(quote)))
        yield score,quote

def _normalized(text):
    # Candidate reconstruction only. Match the saved DP hash before use.
    return re.sub(r'\s+',' ',text.replace('\u00a0',' ')).strip()


def _saved_chunks(text,record):
    source=record.get('data_platform_source')
    chunks=record.get('evidence_chunks')
    if (not isinstance(source,dict) or source.get('offset_space')!='data_platform_normalized_text'
            or not isinstance(chunks,list) or not 1<=len(chunks)<=4096
            or source.get('attributable_chunk_count')!=len(chunks)
            or source.get('source_chunk_count')!=len(chunks)):
        return None
    normalized=_normalized(text)
    result=[]
    ids=set()
    total=0
    for chunk in chunks:
        if not isinstance(chunk,dict):
            return None
        start,end=chunk.get('char_start'),chunk.get('char_end')
        cid=chunk.get('chunk_id')
        if (not isinstance(cid,str) or not cid or cid in ids
                or chunk.get('file_id')!=record.get('file_id')
                or chunk.get('resource_id')!=source.get('resource_id')
                or chunk.get('document_id')!=source.get('document_id')
                or type(start) is not int or type(end) is not int or not 0<=start<end<=len(normalized)):
            return None
        total+=end-start
        if end-start>8192 or total>4*len(normalized)+8192:
            return None
        piece=normalized[start:end].strip()
        if not piece or hashlib.sha256(piece.encode()).hexdigest()!=chunk.get('text_hash'):
            return None
        ids.add(cid)
        result.append(piece)
    return result


def chunk_aligned_clause_candidate(text,terms,record):
    """Preflight against saved chunk hashes; original verifier still mandatory."""
    if terms not in (_EVALUATION,_CONTRACT):
        return _candidate(text,terms)
    chunks=_saved_chunks(text,record)
    if chunks is None:
        return None
    # Do not take sentences out of their original line or splice adjacent chunks.
    # The source quote may use DP's whitespace normalization, never invented text.
    for score,line in nlargest(256,_clause_candidates(text,terms),key=lambda x:x[0]):
        quote=_normalized(line)
        if len(quote)<20:
            continue
        matches=0
        for chunk in chunks:
            if chunk.count(quote)==1:
                matches+=1
            if matches>1:
                break
        if matches==1:
            return score,quote
    return None
