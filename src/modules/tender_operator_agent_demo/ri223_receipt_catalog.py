"""Operator-controlled trust anchor, separate from run/user supplied metadata."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

_SHA = re.compile(r'[a-f0-9]{64}')


def configured_receipts() -> dict[str, dict] | None:
    path = os.environ.get('AI_CORP_RI223_RECEIPT_CATALOG')
    digest = os.environ.get('AI_CORP_RI223_RECEIPT_CATALOG_SHA256')
    if not path and not digest:
        return None
    if not path or not digest or not _SHA.fullmatch(digest):
        raise ValueError('Incomplete RI223 catalog trust anchor')
    source = Path(path)
    if not source.is_absolute() or source.is_symlink() or not source.is_file():
        raise ValueError('Unsafe RI223 catalog')
    with source.open('rb') as f:
        raw = f.read(2_000_001)
    if len(raw)>2_000_000 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('RI223 catalog digest mismatch')
    doc = json.loads(raw)
    if not isinstance(doc,dict) or not isinstance(doc.get('historical_ri223_cases'),list):
        raise TypeError('Invalid RI223 catalog shape')
    rows=doc['historical_ri223_cases']
    if not 0<len(rows)<=500:
        raise ValueError('RI223 catalog size')
    receipts={}
    for row in rows:
        if not isinstance(row,dict):
            raise TypeError('Invalid row')
        n,a,x,v=(row.get(k) for k in ('registry_number','archive_sha256','selected_xml_sha256','observed_version'))
        if not all(isinstance(s,str) for s in (n,a,x,v)) or not re.fullmatch(r'[0-9]{11}',n) or not _SHA.fullmatch(a) or not _SHA.fullmatch(x) or not re.fullmatch(r'[1-9][0-9]{0,5}',v) or n in receipts:
            raise ValueError('Invalid or duplicate RI223 receipt')
        receipts[n]=row
    return receipts


def configured_catalog() -> dict[str, tuple[str, str, str]] | None:
    receipts = configured_receipts()
    if receipts is None:
        return None
    return {n: (r['archive_sha256'], r['selected_xml_sha256'], r['observed_version'])
            for n, r in receipts.items()}
