"""Bounded offline technical text extraction. No macros, external links, or OCR."""
from __future__ import annotations

import hashlib
import io
import os
import select
import time
import tempfile
import unicodedata
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_TEXT=1_000_000
MAX_XML=20_000_000
MAX_ARCHIVE=100_000_000
OFFICE={".docx",".xlsx",".pptx"}
DOCUMENTS=OFFICE|{".pdf",".doc",".xls"}
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


def archive_stream(args, limit, timeout=25):
    # Read only stdout with a byte cap; never unpack on disk or execute members.
    env=dict(os.environ, LC_ALL="en_US.UTF-8")
    proc=subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, env=env, close_fds=True)
    out=bytearray(); deadline=time.monotonic()+timeout
    try:
        while True:
            wait=deadline-time.monotonic()
            if wait<=0 or not select.select([proc.stdout],[],[],wait)[0]:
                raise ValueError("archive read timeout")
            chunk=os.read(proc.stdout.fileno(),65536)
            if not chunk:break
            out.extend(chunk)
            if len(out)>limit:raise ValueError("archive stream size bound")
        if proc.wait(timeout=max(.1,deadline-time.monotonic())):
            raise ValueError("archive read failed")
        return bytes(out)
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)
        proc.stdout.close()


def safe_archive_name(name):
    return (bool(name) and len(name)<=1024 and not name.startswith(("/","-"))
            and not any(ord(c)<32 or c in "\\:*?[]" for c in name)
            and all(p not in ("",".","..") for p in name.rstrip("/").split("/")))


def external_archive_members(path, raw, ext):
    if ext==".rar" and not raw.startswith((b"Rar!\x1a\x07\x00",b"Rar!\x1a\x07\x01\x00")):
        raise ValueError("RAR signature mismatch")
    if ext==".7z" and not raw.startswith(b"7z\xbc\xaf\x27\x1c"):
        raise ValueError("7z signature mismatch")
    tool="/usr/bin/bsdtar"
    names=archive_stream([tool,"-tf",str(path)],256000).decode("utf-8").splitlines()
    verbose=archive_stream([tool,"-tvf",str(path)],512000).decode("utf-8").splitlines()
    if not names or len(names)!=len(verbose) or len(names)>3000:
        raise ValueError("archive listing mismatch")
    entries=[];seen=set();total=0
    for name,line in zip(names,verbose,strict=True):
        key=unicodedata.normalize("NFC",name.rstrip("/")).casefold()
        if not safe_archive_name(name) or key in seen:raise ValueError("unsafe or duplicate archive member")
        seen.add(key)
        if line.startswith("d"):continue
        fields=line.split(maxsplit=5)
        if not line.startswith("-") or len(fields)<6 or not fields[4].isdigit():
            raise ValueError("special member or unknown size")
        size=int(fields[4]);total+=size
        if total>MAX_ARCHIVE or total>len(raw)*200:raise ValueError("archive expansion bound")
        entries.append((name,size))
    for name,size in entries:
        suffix=Path(name).suffix.lower()
        if suffix not in DOCUMENTS or size>25*1024**2:
            yield name,None,"unsupported or oversized member";continue
        try:
            data=archive_stream([tool,"-xOf",str(path),"--",name],size)
            if len(data)!=size:raise ValueError("archive member size mismatch")
            yield name,data,None
        except (ValueError,OSError,subprocess.SubprocessError) as exc:
            yield name,None,str(exc)[:130]


def document_parts(raw,ext):
    if ext in OFFICE:
        yield from office_parts(raw,ext);return
    if ext==".pdf" and not (raw.startswith(b"%PDF-") and b"%%EOF" in raw[-4096:]):
        raise ValueError("invalid PDF")
    if ext in {".doc",".xls"} and not raw.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        # Office files sometimes have the wrong extension; only exact OOXML structure is accepted.
        if raw.startswith(b"PK\x03\x04"):
            yield from office_parts(raw,{".doc":".docx",".xls":".xlsx"}[ext]);return
        raise ValueError("legacy Office signature mismatch")
    with tempfile.TemporaryDirectory(prefix="ta-technical-") as tmp:
        p=Path(tmp)/("document"+ext);p.write_bytes(raw)
        if ext==".pdf":
            text=archive_stream(["/opt/homebrew/bin/pdftotext","-layout",str(p),"-"],MAX_TEXT*4).decode("utf8")
            part="pdf_text_layout"
        elif ext==".doc":
            text=archive_stream(["/usr/bin/textutil","-convert","txt","-stdout",str(p)],MAX_TEXT*4).decode("utf8")
            part="legacy_doc_text"
        elif ext==".xls":
            py=Path.home()/"ArvectumSafe/venvs/ta-technical-xls-20261127/bin/python"
            if not py.is_file():raise ValueError("isolated XLS interpreter unavailable")
            code="""import sys,xlrd
assert xlrd.__version__=='2.0.2'
b=xlrd.open_workbook(sys.argv[1],on_demand=True)
for s in b.sheets():
 print(s.name)
 for i in range(s.nrows): print('\\t'.join(str(v) for v in s.row_values(i)))
b.release_resources()"""
            text=archive_stream([str(py),"-I","-c",code,str(p)],MAX_TEXT*4).decode("utf8")
            part="legacy_xls_cells"
        else:raise ValueError("unsupported document format")
        if not text.strip():raise ValueError("no text layer or empty document")
        yield part,bounded(text)


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
    if ext in DOCUMENTS and ext!=".pdf":
        for part,text in document_parts(raw,ext):
            add(None,expected_sha,part,text)
    elif ext==".zip":
        with safe_zip(raw) as z:
            for info in z.infolist():
                suffix=Path(info.filename).suffix.lower()
                if info.is_dir():
                    continue
                if suffix not in DOCUMENTS or info.file_size>25*1024**2:
                    review.append({"member":info.filename,"reason":"unsupported or oversized member"})
                    continue
                try:
                    data=z.read(info)
                    for part,text in document_parts(data,suffix):
                        add(info.filename,digest(data),part,text)
                except NotImplementedError:
                    # A single unsupported compression method must not poison the
                    # entire batch or masquerade as an extracted document.
                    review.append({"member":info.filename,"reason":"unsupported ZIP compression or member feature",
                                   "compression_method":info.compress_type})
                except (ValueError,KeyError,OSError,subprocess.SubprocessError,ET.ParseError,zipfile.BadZipFile) as exc:
                    review.append({"member":info.filename,"reason":str(exc)[:130]})
    elif ext in {".rar",".7z"}:
        for name,data,error in external_archive_members(path,raw,ext):
            if error:
                review.append({"member":name,"reason":error});continue
            try:
                for part,text in document_parts(data,Path(name).suffix.lower()):
                    add(name,digest(data),part,text)
            except (ValueError,KeyError,OSError,subprocess.SubprocessError,ET.ParseError,zipfile.BadZipFile,NotImplementedError) as exc:
                review.append({"member":name,"reason":str(exc)[:130]})
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
