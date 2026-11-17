"""Dated agency-hosted reproductions; file placement is not legal effectiveness."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path

from lxml import etree

INDEX = 'https://minfin.saratov.gov.ru/index.php?option=com_acrfilestorage&task=download&on='
SOURCES = {
    ('44-ФЗ','2026-11-03'): ('44fz-mchs.docx','77b3f144c27d4f2d6ca4746dbff185e15658930a7abb63727d783a3b2869c894','https://mchs.gov.ru/uploads/document/2026-11-03/60c89dfcdc091527b35b2f58bc537036.docx',{'30':922,'37':1184,'44':1432,'45':1490,'95':2420,'96':2568}),
    ('44-ФЗ','2026-09-11'): ('44fz-saratov.bin','fa1fb2105e586eae5770881ba210363bab9d828dfd319e0dc63ce0f0a6017624',INDEX+'707',{'30':830,'37':1128,'44':1400,'45':1458,'95':2544,'96':2715}),
    ('223-ФЗ','2024-08-21'): ('223fz-saratov.bin','26202e95db2525f4f999aca31e279e3990d08367b757842578321162754496c1',INDEX+'706',{'3':154,'3.2':398,'3.4':471,'4':660}),
    ('223-ФЗ','2025-06-07'): ('223fz-mchs.pdf','a66f63b7a45a6073ce892d93fce16ec8e941ee337ef83de21d42266c38fbb68e','https://mchs.gov.ru/uploads/document/2025-06-07/81c0ff552c6a12324d38e676f727a820.pdf',{'3':(9,3),'3.2':(27,2),'4':(46,6)}),
}
PDF_PROJECTION_SHA='1c84733a321b5cf62702f896a632832e0e059e8f784dfe4fc5f87b1690ed9243'
_NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
_ERRORS=(OSError,ValueError,KeyError,IndexError,TypeError,zipfile.BadZipFile,etree.LxmlError)


def _read(root: Path, name: str, digest: str) -> bytes:
    path=root/name
    if root.is_symlink() or not root.is_dir() or path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=3_000_000:
        raise ValueError('unsafe source')
    with path.open('rb') as f:
        raw=f.read(3_000_001)
    if len(raw)>3_000_000 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('hash mismatch')
    return raw


def _docx_paragraphs(data: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        matches=[i for i in archive.infolist() if i.filename=='word/document.xml']
        if len(matches)!=1 or not 0<matches[0].file_size<=6_000_000:
            raise ValueError('invalid document XML')
        root=etree.fromstring(archive.read(matches[0]),parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False))
        if root.getroottree().docinfo.doctype:
            raise ValueError('unexpected DTD')
        return [' '.join(''.join(p.xpath('.//w:t/text()',namespaces=_NS)).split()) for p in root.xpath('//w:body//w:p',namespaces=_NS)]


def _source(root: Path, act: str, placement: str, article: str | None) -> dict:
    name,digest,url,locators=SOURCES[(act,placement)]
    raw=_read(root,name,digest)
    if name.endswith('.pdf'):
        projection=json.loads(_read(root,'223fz-mchs-blocks.json',PDF_PROJECTION_SHA))
        if projection['raw_sha256']!=digest or projection['page_count']!=65:
            raise ValueError('projection mismatch')
        pages=projection['pages'];header=' '.join(pages['1'][:17])
        if '18 июля 2011 года' not in header or 'N 223-ФЗ' not in header or 'Список изменяющих документов' not in header:
            raise ValueError('identity mismatch')
        if article is not None:
            page,start=locators[article];lines=pages[str(page)]
            if not lines[start-1].startswith('Статья '+article+'. '):raise ValueError('locator mismatch')
            excerpt=lines[start-1];end=start
            if start<len(lines) and not re.match(r'^Статья [0-9]',lines[start]) and len(excerpt)+len(lines[start])+1<=4800:
                excerpt+='\n'+lines[start];end+=1
            locator=f'PDF page {page}, text blocks {start}..{end} (pinned projection)'
            
        else:
            excerpt='\n'.join(x for x in pages['1'][:17] if 'от 08.08.2024' in x)
            locator='PDF page 1, amendment list (pinned projection)'
    else:
        paragraphs=_docx_paragraphs(raw);header=' '.join(paragraphs[:90]);identity='5 апреля 2013 года' if act=='44-ФЗ' else '18 июля 2011 года'
        if identity not in header or 'N '+act not in header or 'Список изменяющих документов' not in header:raise ValueError('identity mismatch')
        if article is not None:
            start=locators[article]
            if not paragraphs[start-1].startswith('Статья '+article+'. '):raise ValueError('locator mismatch')
            selected=[paragraphs[start-1]];end=start
            for i in range(start,len(paragraphs)):
                text=paragraphs[i]
                if re.match(r'^Статья [0-9]',text):break
                if not text:continue
                if len(selected)>=4 or sum(map(len,selected))+len(text)+len(selected)>4800:break
                selected.append(text);end=i+1
            if len(selected)<2:raise ValueError('no bounded excerpt')
            excerpt='\n'.join(selected);locator=f'word/document.xml body p[{start}..{end}] (1-based)'
        else:
            day='04.08.2026' if act=='44-ФЗ' else '08.08.2024'
            selected=[(i+1,p) for i,p in enumerate(paragraphs[:90]) if 'от '+day+' N ' in p]
            if not selected:raise ValueError('missing amendment list')
            excerpt='\n'.join(p for _,p in selected);locator='word/document.xml amendment list p['+','.join(str(i) for i,_ in selected)+']'
    if not excerpt or len(excerpt)>4800:raise ValueError('excerpt bound')
    return {'source_ref':f'government-copy:{digest}:{article or "amendment-list"}', 'document':f'{act}, копия {placement} (дата размещения/пути файла)', 'source_url':url,'source_sha256':digest,'locator':locator,'excerpt':excerpt,'source_kind':'GOVERNMENT_HOSTED_REPRODUCTION','placement_date':placement, 'projection_sha256': PDF_PROJECTION_SHA if name.endswith('.pdf') else None}


def government_copy_observation(act: str, placement: str, article: str) -> dict:
    result={'status':'UNKNOWN','snapshot_bytes_verified':False,'current_law_verified':False,'statute_text_verified':False,'applicability_verified':False,'reviewed_effective_interval':None,'article_complete':False,'legal_conclusion':None,'citations':[]}
    configured=os.environ.get('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    if not configured:return {**result,'reason':'SNAPSHOT_STORAGE_NOT_CONFIGURED'}
    try: cite=_source(Path(configured).expanduser(),act,placement,article)
    except _ERRORS:return {**result,'reason':'GOVERNMENT_COPY_EVIDENCE_UNAVAILABLE'}
    return {**result,'status':'HISTORICAL_STATUTE_SNAPSHOT_EXCERPT','snapshot_bytes_verified':True,'citations':[cite],'reason':'PLACEMENT_DATE_NOT_EFFECTIVE_DATE'}


def compare_government_copies(act: str) -> dict:
    result={'status':'UNKNOWN','current_law_verified':False,'applicability_verified':False,'legal_conclusion':None,'citations':[]}
    configured=os.environ.get('AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR')
    if not configured:return {**result,'reason':'SNAPSHOT_STORAGE_NOT_CONFIGURED'}
    dates=sorted(d for a,d in SOURCES if a==act)
    if len(dates)!=2:return {**result,'reason':'COPY_PAIR_NOT_AVAILABLE'}
    try:cites=[_source(Path(configured).expanduser(),act,d,None) for d in dates]
    except _ERRORS:return {**result,'reason':'GOVERNMENT_COPY_EVIDENCE_UNAVAILABLE'}
    target=('278','279','330') if act=='44-ФЗ' else ('232','318')
    observations=[{'amendment':n+'-ФЗ','listed_in_older_excerpt':bool(re.search(r'\b'+n+r'-ФЗ\b',cites[0]['excerpt'])),'listed_in_newer_excerpt':bool(re.search(r'\b'+n+r'-ФЗ\b',cites[1]['excerpt']))} for n in target]
    return {**result,'status':'GOVERNMENT_COPY_LIST_COMPARISON','citations':cites,'observations':observations,'dates':dates,'amendment_coverage_complete':False}
