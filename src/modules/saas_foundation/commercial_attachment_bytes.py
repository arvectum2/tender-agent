"""Bounded file inspection, not malware scanning or source authentication."""
from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from pathlib import PurePosixPath

from lxml import etree

MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024
MAX_UNPACKED = 12 * 1024 * 1024
MAX_MEMBERS = 180
MAX_PREVIEW_CHARS = 12_000
MAX_PARAGRAPHS = 80
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TYPES = {
    'docx': ('word/document.xml', W+'document', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'),
    'xlsx': ('xl/workbook.xml', '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
    'pptx': ('ppt/presentation.xml', '{http://schemas.openxmlformats.org/presentationml/2006/main}presentation', 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
}
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'


def _xml(raw):
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise ValueError('Oversized package XML')
    text = raw.decode('utf-8-sig', errors='strict')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('Unsafe XML declaration')
    return etree.fromstring(raw, parser=etree.XMLParser(encoding='UTF-8', resolve_entities=False, load_dtd=False, no_network=True, huge_tree=False))


def _inspect_ooxml(raw, kind):
    main, tag, mime = TYPES[kind]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if not members or len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_UNPACKED:
            raise ValueError('Package expansion limit exceeded')
        names = set()
        for m in members:
            name = m.filename
            path = PurePosixPath(name)
            lowered = name.casefold()
            if (not name or '\\' in name or ':' in name or '\x00' in name or path.is_absolute()
                    or any(x in {'.', '..'} for x in name.rstrip('/').split('/')) or lowered in names
                    or m.flag_bits & 1 or stat.S_ISLNK(m.external_attr >> 16)
                    or m.file_size > MAX_ATTACHMENT_BYTES or m.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or any(x in lowered for x in ('vbaproject', 'activex/', 'embeddings/', 'oleobject'))):
                raise ValueError('Unsafe package member')
            names.add(lowered)
        if '[content_types].xml' not in names or main.casefold() not in names:
            raise ValueError('Missing expected package parts')
        # Read bounded members to check CRC; never extract to disk.
        for m in members:
            if not m.is_dir():
                data = archive.read(m)
                if m.filename.casefold().endswith('.rels'):
                    rels = _xml(data)
                    if any(x.get('TargetMode', '').casefold() == 'external' for x in rels.iter()):
                        raise ValueError('External package relationship')
        content = _xml(archive.read('[Content_Types].xml'))
        matches = [n for n in content.findall(CT+'Override') if n.get('PartName') == '/'+main]
        if content.tag != CT+'Types' or len(matches) != 1 or matches[0].get('ContentType') != mime or any('macroenabled' in n.get('ContentType','').casefold() for n in content):
            raise ValueError('Package content type mismatch')
        root = _xml(archive.read(main))
        if root.tag != tag:
            raise ValueError('Package main XML mismatch')
        paragraphs = []
        if kind == 'docx':
            body = root.find(W+'body')
            if body is None:
                raise ValueError('Missing document body')
            remaining = MAX_PREVIEW_CHARS
            for i, p in enumerate(body.iter(W+'p'), 1):
                if len(paragraphs) >= MAX_PARAGRAPHS or remaining <= 0:
                    break
                value = ' '.join(''.join(t.text or '' for t in p.iter(W+'t')).split())
                if value:
                    value = value[:remaining]
                    paragraphs.append({'part': main, 'paragraph_index': i, 'text': value})
                    remaining -= len(value)
        return paragraphs


def inspect_attachment(raw: bytes, kind: str) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_ATTACHMENT_BYTES:
        raise ValueError('Attachment size limit exceeded')
    if kind == 'pdf':
        if not re.match(rb'%PDF-[12]\.[0-9](?:\r|\n)', raw) or not raw.rstrip().endswith(b'%%EOF'):
            raise ValueError('PDF signature mismatch')
        preview = []
        validation = 'PDF_HEADER_AND_EOF_ONLY'
    elif kind in TYPES:
        try:
            preview = _inspect_ooxml(raw, kind)
        except (zipfile.BadZipFile, RuntimeError, KeyError, OSError, etree.LxmlError, UnicodeError) as exc:
            raise ValueError('Invalid bounded OOXML package') from exc
        validation = 'BOUNDED_OOXML_PACKAGE_CHECK'
    else:
        raise ValueError('Unsupported attachment format')
    return {'schema':'commercial_attachment_inspection_v1','sha256':hashlib.sha256(raw).hexdigest(),
            'size_bytes':len(raw),'format_hint':kind,'format_check':validation,
            'text_preview':preview,'text_preview_complete':False,'requirements_verified':False,
            'malware_free_verified':False,'digital_signature_verified':False}
