"""Versioned read-only text projection; never certify requirements or source origin."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml.etree import LxmlError

from src.modules.saas_foundation.commercial_attachment_bytes import (
    _xml,
    inspect_attachment,
)

S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
MAX_FRAGMENTS = 80
MAX_CHARS = 12000
MAX_FRAGMENT = 1000
MAX_PDF_OUTPUT = 256 * 1024
# Separate helper process: no preexec_fn in a threaded web server.
_LIMITED_EXEC = '''import os,resource,sys
resource.setrlimit(resource.RLIMIT_CPU,(5,5))
resource.setrlimit(resource.RLIMIT_FSIZE,(262144,262144))
if sys.platform.startswith('linux'): resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
os.execv(sys.argv[1],sys.argv[1:])'''


def _xlsx(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        wb = _xml(z.read('xl/workbook.xml'))
        rel = _xml(z.read('xl/_rels/workbook.xml.rels'))
        if rel.tag != PR+'Relationships':
            raise ValueError('Invalid workbook relationships')
        targets = {}
        for item in rel.findall(PR+'Relationship'):
            key, target = item.get('Id'), item.get('Target','')
            if not key or key in targets:
                raise ValueError('Ambiguous workbook relationship')
            if item.get('Type') == R[1:-1]+'/worksheet':
                if not re.fullmatch(r'/?(?:xl/)?worksheets/sheet[0-9]+\.xml',target):
                    raise ValueError('Unsupported worksheet path')
                targets[key] = 'xl/'+target.lstrip('/').removeprefix('xl/')
            else:
                targets[key] = None
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(t.text or '' for t in e.iter(S+'t')) for e in _xml(z.read('xl/sharedStrings.xml')).findall(S+'si')]
        seen = set()
        sheet_nodes = wb.findall(S+'sheets/'+S+'sheet')
        if not sheet_nodes:
            raise ValueError('No worksheet metadata')
        for sheet in sheet_nodes:
            name = sheet.get('name','')
            target = targets.get(sheet.get(R+'id'))
            if not name or len(name)>31 or name.casefold() in seen or not target:
                raise ValueError('Ambiguous worksheet identity')
            seen.add(name.casefold())
            if sheet.get('state','visible') != 'visible':
                continue
            part = _xml(z.read(target))
            if part.tag != S+'worksheet':
                raise ValueError('Worksheet format mismatch')
            cells = set()
            for cell in part.iter(S+'c'):
                addr = cell.get('r','')
                if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}',addr) or addr in cells:
                    raise ValueError('Ambiguous cell identity')
                cells.add(addr)
                # Never evaluate formulas, cached formulas, dates, or inferred units.
                if cell.find(S+'f') is not None:
                    continue
                kind = cell.get('t','n'); value = cell.findtext(S+'v')
                if kind == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.iter(S+'t'))
                elif kind == 's':
                    if not value or not re.fullmatch(r'[0-9]{1,8}',value) or int(value)>=len(strings):
                        raise ValueError('Invalid shared string reference')
                    value = strings[int(value)]
                elif kind not in {'n','str','b'}:
                    continue
                if value:
                    yield {'part':target,'sheet':name,'cell':addr,'text':value}


def _pdf(raw):
    executable = shutil.which('pdftotext')
    if not executable:
        return 'EXTRACTOR_UNAVAILABLE', []
    with tempfile.TemporaryDirectory(prefix='commercial-text-') as tmp:
        source, output = Path(tmp)/'original.pdf',Path(tmp)/'text.txt'
        source.write_bytes(raw)
        # No shell, user-controlled flags, inherited credentials, or rendering.
        try:
            result = subprocess.run([sys.executable,'-I','-c',_LIMITED_EXEC,executable,'-f','1','-l','8','-enc','UTF-8',str(source),str(output)],cwd=tmp,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8,check=False)
            if result.returncode or not output.is_file() or output.stat().st_size > MAX_PDF_OUTPUT:
                return 'EXTRACTION_UNAVAILABLE', []
            pages = output.read_bytes().decode('utf-8',errors='strict').split('\f')[:8]
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            return 'EXTRACTION_UNAVAILABLE', []
    return 'PARTIAL_PREVIEW', [{'page':i,'line_index':j,'text':line} for i,page in enumerate(pages,1) for j,line in enumerate(page.splitlines(),1) if line.strip()]


_MARKERS = {
    'qualification': re.compile(r'квалификац|опыт.{0,40}(работ|постав|исполн)|референс|лицензи|сертификат',re.IGNORECASE),
    'delivery': re.compile(r'срок.{0,40}(постав|выполн|оказан|передач)|место поставки',re.IGNORECASE),
    'payment': re.compile(r'оплат|аванс|отсрочк|обеспечен',re.IGNORECASE),
    'technical': re.compile(r'должен|должна|должны|необходимо|требовани|обязательн',re.IGNORECASE),
}


def project_text(raw, kind, *, pdf_enabled=False):
    inspected=inspect_attachment(raw,kind)
    status='PARTIAL_PREVIEW'
    try:
        if kind=='docx':
            fragments=inspected['text_preview']
        elif kind=='xlsx':
            fragments=_xlsx(raw)
        elif kind=='pdf' and pdf_enabled:
            status,fragments=_pdf(raw)
        else:
            status,fragments='EXTRACTION_DISABLED_OR_UNSUPPORTED',[]
        rows=[];remain=MAX_CHARS
        for fragment in fragments:
            if len(rows)>=MAX_FRAGMENTS or remain<=0:break
            text=' '.join(fragment['text'].split())
            if not text:continue
            take=min(remain,MAX_FRAGMENT);value=text[:take];remain-=len(value)
            location={k:v for k,v in fragment.items() if k!='text'}
            rows.append({'fragment_id':len(rows)+1,'location':location,'text':value,'fragment_truncated':len(text)>len(value)})
    except (ValueError,KeyError,OSError,zipfile.BadZipFile,LxmlError):
        status,rows='EXTRACTION_UNAVAILABLE',[]
    if status=='PARTIAL_PREVIEW' and not rows:status='NO_READABLE_TEXT_IN_PREVIEW'
    candidates=[{'fragment_id':row['fragment_id'],'categories':[k for k,p in _MARKERS.items() if p.search(row['text'])],'review_state':'UNREVIEWED_LITERAL_MATCH'} for row in rows if any(p.search(row['text']) for p in _MARKERS.values())]
    return {'schema':'commercial_text_projection_v1','source_sha256':inspected['sha256'],'status':status,'fragments':rows,'requirement_candidates':candidates,'coverage_complete':False,'requirements_verified':False,'platform_original_verified':False,'qualification_verified':False,'external_submission_allowed':False}
