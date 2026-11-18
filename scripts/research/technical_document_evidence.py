"""Bounded offline technical text extraction. No macros, external links, or OCR."""
from __future__ import annotations

import hashlib
import io
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_TEXT=1_000_000
MAX_XML=20_000_000
MAX_ARCHIVE=100_000_000
OFFICE={".docx",".xlsx",".pptx"}
PATTERNS={
    "pq_equipment":r"\b(?:УКРМ|STATCOM|СТАТКОМ|SVC|SVG|АФГ|активн\w+\s+фильтр\w+\s+гармоник|статическ\w+\s+компенсатор\w*|тиристорн\w+\s+компенсатор\w*)\b|установк\w+\s+компенсаци\w*\s+реактивн\w+\s+мощност\w*|фильтр\w*\s+(?:высш\w+\s+)?гармоник\w*|конденсаторн\w+\s+установк\w*",
    "pq_requirement":r"компенсаци\w*\s+реактивн\w+\s+мощност\w*|реактивн\w+\s+мощност\w*|качество\s+электр(?:оэнерги\w*|ическ\w+\s+энерги\w*)|коэффициент\w*\s+мощност\w*|коэффициент\w*\s+гармоническ\w+|\b(?:THD|cos\s*φ|cos\s*phi)\b|несинусоидальност\w*",
    "electrical":r"\b(?:КРУ|КТП|РЗА)\b|трансформатор\w*|электропривод\w*|частотн\w+\s+преобразовател\w*",
    "automation":r"\b(?:АСУ\s*ТП|КИПиА|КИП|ПТК)\b|телемеханик\w*|контроллер\w*",
    "engineering":r"проектирован\w*|пусконаладочн\w*|модернизац\w*|техническ\w+\s+перевооруж\w*"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_zip(raw):
    z=zipfile.ZipFile(io.BytesIO(raw))
    infos=z.infolist()
    if (len(infos)>3000 or sum(i.file_size for i in infos)>MAX_ARCHIVE
            or any(i.flag_bits&1 for i in infos)
            or len({i.filename for i in infos})!=len(infos)):
        z.close()
        raise ValueError("archive bounds or encryption")
    return z


def xml_part(z,name):
    info=z.getinfo(name)
    if info.file_size>MAX_XML:
        raise ValueError("XML size bound")
    raw=z.read(info)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML declaration rejected")
    return ET.fromstring(raw)


def local(tag):
    return tag.rsplit("}",1)[-1]


def bounded(text):
    if len(text)>MAX_TEXT:
        raise ValueError("text limit; no complete extraction claim")
    return text


def office_parts(raw,ext):
    with safe_zip(raw) as z:
        names=set(z.namelist())
        if ext==".docx":
            root=xml_part(z,"word/document.xml")
            text="\n".join("".join(t.text or "" for t in p.iter() if local(t.tag)=="t")
                           for p in root.iter() if local(p.tag)=="p")
            yield "word/document.xml",bounded(text)
        elif ext==".xlsx":
            shared=[]
            if "xl/sharedStrings.xml" in names:
                root=xml_part(z,"xl/sharedStrings.xml")
                shared=["".join(t.text or "" for t in si.iter() if local(t.tag)=="t") for si in root if local(si.tag)=="si"]
            for name in sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",n)):
                root=xml_part(z,name)
                lines=[]
                for row in root.iter():
                    if local(row.tag)!="row":
                        continue
                    cells=[]
                    for c in row:
                        if local(c.tag)!="c":
                            continue
                        val=next((v.text or "" for v in c if local(v.tag)=="v"),"")
                        if c.get("t")=="s":
                            if not val.isdecimal() or int(val)>=len(shared):
                                raise ValueError("invalid shared string reference")
                            val=shared[int(val)]
                        elif c.get("t")=="inlineStr":
                            val="".join(t.text or "" for t in c.iter() if local(t.tag)=="t")
                        cells.append(val)
                    lines.append("\t".join(cells))
                yield name,bounded("\n".join(lines))
        elif ext==".pptx":
            for name in sorted(n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml",n)):
                root=xml_part(z,name)
                yield name,bounded("\n".join("".join(t.text or "" for t in p.iter() if local(t.tag)=="t")
                                             for p in root.iter() if local(p.tag)=="p"))
        else:
            raise ValueError("unsupported office format")


def matches(text):
    result={}
    for category,pattern in PATTERNS.items():
        hits=[]
        for m in re.finditer(pattern,text,re.IGNORECASE):
            a,b=max(0,m.start()-90),min(len(text),m.end()+90)
            hits.append({"start":m.start(),"end":m.end(),"match":m.group(),"excerpt_start":a,"excerpt_end":b,"excerpt":text[a:b]})
            if len(hits)>=30:
                break
        if hits:
            result[category]=hits
    return result


def extract(path,expected_sha):
    if path.is_symlink() or path.stat().st_size>25*1024**2:
        raise ValueError("original bounds")
    raw=path.read_bytes()
    if digest(raw)!=expected_sha:
        raise ValueError("original SHA mismatch")
    ext=path.suffix.lower()
    parts=[];review=[]
    def add(member,member_sha,part,text):
        parts.append({"member":member,"member_sha256":member_sha,"part":part,"text_sha256":digest(text.encode()),
                      "chars":len(text),"matches":matches(text)})
    if ext in OFFICE:
        for part,text in office_parts(raw,ext):
            add(None,expected_sha,part,text)
    elif ext==".zip":
        with safe_zip(raw) as z:
            for info in z.infolist():
                suffix=Path(info.filename).suffix.lower()
                if info.is_dir():
                    continue
                if suffix not in OFFICE or info.file_size>25*1024**2:
                    review.append({"member":info.filename,"reason":"unsupported or oversized member"})
                    continue
                try:
                    data=z.read(info)
                    for part,text in office_parts(data,suffix):
                        add(info.filename,digest(data),part,text)
                except NotImplementedError:
                    # A single unsupported compression method must not poison the
                    # entire batch or masquerade as an extracted document.
                    review.append({"member":info.filename,"reason":"unsupported ZIP compression or member feature",
                                   "compression_method":info.compress_type})
                except (ValueError,KeyError,ET.ParseError,zipfile.BadZipFile) as exc:
                    review.append({"member":info.filename,"reason":str(exc)[:130]})
    elif ext==".pdf":
        if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-4096:]:
            raise ValueError("invalid PDF")
        proc=subprocess.run(["/opt/homebrew/bin/pdftotext","-layout",str(path),"-"],capture_output=True,timeout=15,check=True)
        text=bounded(proc.stdout.decode("utf8"))
        if not text.strip():
            review.append({"member":None,"reason":"no text layer"})
        else:
            add(None,expected_sha,"pdf_text_layout",text)
    else:
        review.append({"member":None,"reason":"unsupported container or legacy format"})
    return {"schema":"technical_document_evidence_v1","source_sha256":expected_sha,
            "verification":"LEXICAL_HITS_NOT_CONFIRMED_SCOPE_OR_AWARD",
            "parts":parts,"review":review,"status":"partial_review" if review else ("extracted" if parts else "empty")}
