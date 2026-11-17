"""Offline versioned snapshots; never infer an effective legal edition."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree, html


@dataclass(frozen=True)
class StatuteSnapshot:
    act: str
    act_date: str
    stated_snapshot_date: str
    source_url: str
    source_kind: str
    filename: str
    sha256: str
    edition_marker: str
    identity_marker: str


CATALOG_VERSION = 'procurement-law-snapshots-v1'
SNAPSHOTS = (
    StatuteSnapshot(
        act='44-ФЗ', act_date='2013-04-05', stated_snapshot_date='2022-07-14',
        source_url='https://rospatent.gov.ru/ru/documents/fed-zakon-44-05042013',
        source_kind='GOVERNMENT_WEBSITE_HISTORICAL_REPRODUCTION', filename='44fz-rospatent.html',
        sha256='8cc95985d65d6913861ca42d4b67fd2ce42adca25a132ce17c82e03d052d433d',
        edition_marker='(с изменениями на 14 июля 2022 года)',
        identity_marker='Федеральный закон от 5 апреля 2013 года № 44-ФЗ',
    ),
)
MAX_BLOB_BYTES = 3_000_000
MAX_EXCERPT_CHARS = 4800
_HEADING = re.compile(r'^Статья ([0-9]{1,3}(?:\.[0-9]{1,2})?)\.\s+\S')


def _normalize(text: str) -> str:
    return ' '.join(text.split())


def lookup_statute_snapshot(*, act: str, article: str, requested_date: str, mode: str) -> dict[str, Any]:
    result: dict[str, Any] = {'status': 'UNKNOWN', 'catalog_version': CATALOG_VERSION,
        'act': act, 'article': article, 'requested_date': requested_date, 'lookup_mode': mode,
        'snapshot_bytes_verified': False, 'statute_text_verified': False,
        'current_law_verified': False, 'applicability_verified': False,
        'reviewed_effective_interval': None, 'article_complete': False, 'legal_conclusion': None,
        'citations': []}
    try:
        if date.fromisoformat(requested_date).isoformat() != requested_date:
            raise ValueError('noncanonical date')
    except (TypeError, ValueError):
        return {**result, 'reason': 'INVALID_DATE'}
    if mode != 'explicit_snapshot':
        return {**result, 'reason': 'NO_REVIEWED_EFFECTIVE_INTERVAL'}
    candidates = [s for s in SNAPSHOTS if (s.act, s.stated_snapshot_date) == (act, requested_date)]
    if len(candidates) != 1:
        return {**result, 'reason': 'SNAPSHOT_NOT_UNIQUE_OR_MISSING'}
    snapshot = candidates[0]
    configured = os.environ.get('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    if not configured:
        return {**result, 'reason': 'SNAPSHOT_STORAGE_NOT_CONFIGURED'}
    root = Path(configured).expanduser()
    path = root / snapshot.filename
    try:
        if root.is_symlink() or not root.is_dir() or path.is_symlink() or not path.is_file() or not (0 < path.stat().st_size <= MAX_BLOB_BYTES):
            return {**result, 'reason': 'SNAPSHOT_FILE_UNSAFE_OR_MISSING'}
        with path.open('rb') as f:
            data = f.read(MAX_BLOB_BYTES + 1)
        if len(data) > MAX_BLOB_BYTES or hashlib.sha256(data).hexdigest() != snapshot.sha256:
            return {**result, 'reason': 'SNAPSHOT_HASH_MISMATCH'}
        tree = html.fromstring(data.decode('utf-8'), parser=html.HTMLParser(no_network=True, recover=False))
    except (OSError, ValueError, etree.LxmlError):
        return {**result, 'reason': 'SNAPSHOT_READ_OR_PARSE_FAILED'}
    paragraphs = [_normalize(p.text_content()) for p in tree.xpath('//p')]
    identity = [_normalize(t.text_content()) for t in tree.xpath('//h1|//h2|//h3|//h4')]
    if paragraphs.count(snapshot.edition_marker) != 1 or snapshot.identity_marker not in identity:
        return {**result, 'reason': 'SNAPSHOT_IDENTITY_OR_EDITION_UNVERIFIED'}
    headings = [(i, m[1]) for i, p in enumerate(paragraphs) if (m := _HEADING.match(p))]
    matching = [i for i, number in headings if number == article]
    if len(matching) != 1:
        return {**result, 'reason': 'ARTICLE_NOT_UNIQUE_OR_MISSING'}
    start = matching[0]
    end = next((i for i, _ in headings if i > start), None)
    if end is None:
        return {**result, 'reason': 'ARTICLE_END_NOT_BOUNDED'}
    selected = [paragraphs[start]]
    last = start
    for i in range(start + 1, end):
        if not paragraphs[i]:
            continue
        if len(selected) >= 4 or sum(map(len, selected)) + len(paragraphs[i]) + len(selected) > MAX_EXCERPT_CHARS:
            break
        selected.append(paragraphs[i])
        last = i
    if len(selected) < 2:
        return {**result, 'reason': 'BOUNDED_EXCERPT_UNAVAILABLE'}
    citation = {'source_ref': f'legal-snapshot:{snapshot.sha256}:article:{article}',
        'document': f'{act} от {snapshot.act_date}, снимок с изменениями на {snapshot.stated_snapshot_date}',
        'locator': f'HTML p[{start+1}..{last+1}] (1-based; normalized whitespace)',
        'excerpt': '\n'.join(selected), 'source_url': snapshot.source_url,
        'source_sha256': snapshot.sha256, 'source_kind': snapshot.source_kind,
        'stated_snapshot_date': snapshot.stated_snapshot_date}
    return {**result, 'status': 'HISTORICAL_STATUTE_SNAPSHOT_EXCERPT', 'snapshot_bytes_verified': True,
        'citations': [citation], 'reason': 'HISTORICAL_REPRODUCTION_ONLY'}
