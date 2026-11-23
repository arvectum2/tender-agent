"""Offline real copy acceptance. Optional local PyMuPDF independently replays PDF projection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from src.modules.tender_operator_agent_demo.evidence_government_copies import (
    PDF_PROJECTION_SHA,
    SOURCES,
    compare_government_copies,
    government_copy_observation,
)


def main() -> int:
    import pymupdf

    root=Path(os.environ['AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR'])
    pdf=root/'223fz-mchs.pdf'
    with pymupdf.open(pdf) as doc:
        out={'raw_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'page_count':len(doc),'extractor':'pymupdf '+pymupdf.VersionBind,'pages':{}}
        for page in [1,9,27,32,46]:
            out['pages'][str(page)]=[' '.join(x[4].split()) for x in doc[page-1].get_text('blocks',sort=True) if x[6]==0]
    assert hashlib.sha256(json.dumps(out,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==PDF_PROJECTION_SHA
    count=0
    for (act,placement),item in SOURCES.items():
        for article in item[3]:
            r=government_copy_observation(act,placement,article)
            assert r['status']=='HISTORICAL_STATUTE_SNAPSHOT_EXCERPT' and not r['current_law_verified'] and not r['statute_text_verified']
            assert r['citations'][0]['excerpt'].startswith(f'Статья {article}. ')
            count+=1
    for act,number in [('44-ФЗ','278-ФЗ'),('223-ФЗ','318-ФЗ')]:
        r=compare_government_copies(act)
        assert r['status']=='GOVERNMENT_COPY_LIST_COMPARISON'
        assert {'amendment':number,'listed_in_older_excerpt':False,'listed_in_newer_excerpt':True} in r['observations']
    print('APR08_GOVERNMENT_COPIES_REPLAY_PASS',count,'article excerpts; two comparisons; PDF projection independently re-extracted')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
