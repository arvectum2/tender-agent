"""Operator pilot for public discovery and an explicitly authorized B2B download.

Documented UI only. No automatic login, application, payment, CAPTCHA solving,
method guessing, or private endpoint probing. Not connected to production.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

from src.modules.saas_foundation.commercial_sources import commercial_identity

MAX_ARCHIVE = 25 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_FILES = 200
B2B_FLOW = ('Позиции', 'Скачать файлом', 'Закупочная документация')
WORKSPACE_RESTRICTIONS = ('файлы для скачивания доступны участникам с pro-аккаунтом', 'файлы для скачивания будут доступны исполнителям с базовым аккаунтом после отклика')


def route_permitted(card_url, request_url, method, resource_type):
    original, target = urlsplit(card_url), urlsplit(request_url)
    return (target.scheme=='https' and target.netloc==original.netloc and not target.username and not target.password
            and method in {'GET','HEAD'} and resource_type not in {'image','font','media','websocket'})


def plan(card_url, body, controls, *, authenticated=False):
    platform, identifier = commercial_identity(card_url)
    normalized=' '.join(body.casefold().replace('ё','е').split())
    if any(word in normalized for word in ('captcha','подтвердите, что вы не робот','проверка браузера')):
        state='ACCESS_CHALLENGE'
    elif platform=='workspace' and any(s in normalized for s in WORKSPACE_RESTRICTIONS):
        state='WORKSPACE_ENTITLEMENT_REQUIRED'
    elif platform=='b2bcenter' and authenticated and B2B_FLOW[0] in controls and re.search(r'(?<!\d)'+identifier+r'(?!\d)',body):
        state='B2B_DOCUMENTED_UI_READY'
    elif platform=='b2bcenter':
        state='B2B_AUTHORIZED_UI_OR_API_REQUIRED'
    else:
        state='NO_VERIFIED_DOWNLOAD_CONTROL'
    return {'platform':platform,'external_id':identifier,'state':state,'source_url':card_url,
            'official_api':'CABINET_METHOD_CONTRACT_REQUIRED' if platform=='b2bcenter' else 'NO_PUBLIC_DOCUMENT_API_CONFIRMED',
            'source_document_bytes_verified':False,'complete_documentation_verified':False,'external_submission_allowed':False}


def archive_receipt(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=MAX_ARCHIVE:
        raise ValueError('Archive exceeds size limit or is not a regular file')
    try:
        with ZipFile(path) as z:
            members=z.infolist()
            if not members or len(members)>MAX_FILES or sum(x.file_size for x in members)>MAX_EXPANDED:
                raise ValueError('Archive expansion limit')
            names=set();files=[]
            for x in members:
                n=x.filename; p=PurePosixPath(n)
                if (not n or p.is_absolute() or '\\' in n or ':' in n or '..' in p.parts or n.casefold() in names or x.flag_bits&1 or (x.external_attr>>16)&0o170000==0o120000):
                    raise ValueError('Unsafe archive member')
                names.add(n.casefold())
                if not x.is_dir():files.append({'name':n,'size_bytes':x.file_size})
            if not files or z.testzip() is not None:raise ValueError('Invalid archive content')
    except (BadZipFile,RuntimeError,OSError,NotImplementedError) as exc:
        raise ValueError('Invalid original ZIP') from exc
    with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'sha256':sha,'size_bytes':path.stat().st_size,'members':files,'format_check':'BOUNDED_ZIP_CRC','malware_free_verified':False,'complete_documentation_verified':False}


def _unique_visible(page,label):
    # Exact visible UI label; never choose another control on ambiguity.
    candidates=page.get_by_text(label,exact=True)
    visible=[candidates.nth(i) for i in range(candidates.count()) if candidates.nth(i).is_visible()]
    if len(visible)!=1:raise ValueError('Missing or ambiguous documented control')
    return visible[0]


def observe(page, card_url, *, authenticated=False):
    if page.url!=card_url:raise ValueError('Card navigation identity mismatch')
    body=page.locator('body').inner_text(timeout=3000)
    if len(body)>500000:raise ValueError('Bounded body exceeded')
    controls=[]
    for label in B2B_FLOW:
        try:_unique_visible(page,label)
        except ValueError:continue
        controls.append(label)
    result=plan(card_url,body,controls,authenticated=authenticated)
    result['visible_controls']=controls
    result['body_sha256']=hashlib.sha256(body.encode()).hexdigest()
    return result


def download_b2b(page,card_url,destination,*,authorized):
    if not authorized or observe(page,card_url,authenticated=True)['state']!='B2B_DOCUMENTED_UI_READY':
        raise ValueError('Explicit authorized B2B card and exact identity required')
    for label in B2B_FLOW[:2]:
        _unique_visible(page,label).click(timeout=4000)
        if page.url!=card_url:raise ValueError('Unexpected navigation')
    with page.expect_download(timeout=12000) as event:
        _unique_visible(page,B2B_FLOW[2]).click(timeout=4000)
    download=event.value
    if not route_permitted(card_url,download.url,'GET','document') or not download.suggested_filename.casefold().endswith('.zip') or page.url!=card_url:
        download.cancel();raise ValueError('Unexpected download source or format')
    if Path(destination).exists():raise ValueError('Destination already exists')
    download.save_as(str(destination))
    return archive_receipt(destination)
