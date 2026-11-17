"""Cross-checked secondary-source commencement schedule, not applicable law."""
from __future__ import annotations

import hashlib
import os
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree, html

SOURCES = (
    ('279-article2-consultant.html', '0f4a77038e3a978067195f15120ee921e4f431802a31e61d7c5cc386f57564f3', 'https://www.consultant.ru/document/cons_doc_LAW_540928/b004fed0b70d0f223e4a81f8ad6cd92af90a7e3b/', (3,4,5)),
    ('279-article2-garant.html', '949dc8a603f4514abe837cc1ced14079204ae89767734a11e471813eca202aa3', 'https://base.garant.ru/414699397/741609f9002bd54a24e5c49cb5af953b/', (2,3,4)),
    ('base_garant_ru_414699397_.html', '06d7d219f8a51580ce88e0952133c8d0cfd453769fc0e740c091b67bb6413bd9', 'https://base.garant.ru/414699397/', (25,)),
)
CLAUSE_HASHES = ('6d2feab860647b6999ff97c5c9ffd01cffc58962f4ec9f57bf3a31d37bdab61e', 'f7cbaac327dd7cfd65a65bd639295e92de40f52103d5c995f677e044afffbd19', '60ce07eb757f5b785ed11a428fe01754d0a5b7bb966d4a844a41d418ad3e95e4')
PUBLICATION_LITERAL = 'официальный интернет-портал правовой информации (pravo.gov.ru) 4 августа 2026 г. № 0001202608040004'


def _read_source(root: Path, source: tuple) -> tuple[list[str], dict] | None:
    filename, digest, url, indexes = source
    path = root / filename
    try:
        if root.is_symlink() or not root.is_dir() or path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 3000000:
            return None
        with path.open('rb') as file:
            raw = file.read(3000001)
        if len(raw)>3000000 or hashlib.sha256(raw).hexdigest()!=digest:
            return None
        parsed = html.fromstring(raw, parser=html.HTMLParser(no_network=True, recover=True))
        paragraphs = [' '.join(e.text_content().split()) for e in parsed.xpath('//p')]
        lines = [paragraphs[i-1] for i in indexes]
    except (OSError, ValueError, IndexError, etree.LxmlError):
        return None
    return lines, {'source_ref': 'amendment-snapshot:'+digest, 'document': '279-ФЗ от 04.08.2026 — справочная копия',
                   'source_sha256': digest, 'source_url': url, 'locator': 'HTML p['+','.join(map(str,indexes))+'] (1-based)',
                   'excerpt': '\n'.join(lines), 'source_kind': 'SECONDARY_LEGAL_REFERENCE'}


def amendment_timing(requested_date: str) -> dict[str, Any]:
    result: dict[str, Any] = {'status':'UNKNOWN','requested_date':requested_date,'act':'279-ФЗ','amends':'44-ФЗ',
        'official_publication_verified':False,'official_statute_text_verified':False,'consolidated_edition_verified':False,
        'applicability_verified':False,'legal_conclusion':None,'groups':[],'citations':[]}
    try:
        requested = date.fromisoformat(requested_date)
        if requested.isoformat()!=requested_date:raise ValueError('noncanonical')
    except (ValueError, TypeError):return {**result,'reason':'INVALID_DATE'}
    configured = os.environ.get('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    if not configured:return {**result,'reason':'SNAPSHOT_STORAGE_NOT_CONFIGURED'}
    sources = [_read_source(Path(configured).expanduser(), s) for s in SOURCES]
    if any(s is None for s in sources):return {**result,'reason':'AMENDMENT_EVIDENCE_UNAVAILABLE'}
    first, second, publication = sources
    clauses = first[0]
    if clauses != second[0] or tuple(hashlib.sha256(t.encode()).hexdigest() for t in clauses)!=CLAUSE_HASHES or publication[0]!=[PUBLICATION_LITERAL]:
        return {**result,'reason':'AMENDMENT_EVIDENCE_CONFLICT'}
    groups = []
    for index, scope, day, basis in [(1,'Общее правило, кроме исключений статьи 2','2026-10-01','EXPLICIT_CLAUSE_DATE'),(2,'Подпункт в пункта 5 статьи 1','2026-08-04','SECONDARY_REPORTED_PUBLICATION_DATE'),(3,'Пункты 2, 4; подпункт б пункта 5; подпункт б пункта 7; подпункт а пункта 8 статьи 1','2027-01-01','EXPLICIT_CLAUSE_DATE')]:
        groups.append({'article2_part':index,'scope':scope,'stated_start_date':day,'date_basis':basis,
            'calendar_relation':'DATE_REACHED' if requested>=date.fromisoformat(day) else 'FUTURE_DATE',
            'effective_status_verified':False,'clause_literal':clauses[index-1]})
    return {**result,'status':'SECONDARY_AMENDMENT_TIMING_ONLY','reason':'OFFICIAL_PUBLICATION_NOT_VERIFIED',
        'groups':groups,'citations':[s[1] for s in sources],'secondary_copies_agree':True}
