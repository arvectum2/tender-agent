"""Opt-in, receipt-bound container projection; never unpack to archive-supplied paths."""
from __future__ import annotations

import hashlib
import io
import stat
import zipfile
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from src.tender_research.providers.ri223_rar_members import (
    Ri223RarMember,
    extract_ri223_rar_members,
)

# Search workspace has a 24-file bound, including notice and original attachment.
MAX_MEMBERS = 22
MAX_MEMBER_BYTES = 12 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
PROCESSABLE_MEMBERS = frozenset({'.doc', '.docx', '.pdf', '.xlsx', '.xls', '.txt', '.csv'})


def project_rar(content: bytes):
    """Process a private snapshot of already verified container bytes."""
    with TemporaryDirectory(prefix='ri223-rar-') as tmp:
        path = Path(tmp) / 'original.rar'
        path.write_bytes(content)
        members = extract_ri223_rar_members(path)
    if not 0 < len(members) <= MAX_MEMBERS or sum(len(m.content) for m in members) > MAX_EXPANDED_BYTES:
        raise ValueError('RAR projection outside workspace budget')
    seen = set()
    for m in members:
        p = PurePosixPath(m.path)
        if (p.is_absolute() or any(x in ('', '.', '..') for x in m.path.split('/'))
                or any(c in m.path for c in ('\\', '*', '?', '[', ']', '\ufffd'))
                or any(ord(c) < 32 for c in m.path)
                or len(m.path) > 1024 or len(p.parts) > 8 or p.name != m.filename
                or len(m.filename) > 260 or m.path in seen
                or p.suffix.lower() not in PROCESSABLE_MEMBERS
                or not 0 < len(m.content) <= MAX_MEMBER_BYTES):
            raise ValueError('Unverified RAR member')
        seen.add(m.path)
    return members


def member_receipt(parent_sha: str, member, *, container_format: str = 'RAR') -> dict:
    return {'parent_sha256': parent_sha, 'member_path': member.path,
            'member_sha256': hashlib.sha256(member.content).hexdigest(),
            'member_bytes': len(member.content), 'container_format': container_format}

MAX_ZIP_ENTRIES = 64
MAX_ZIP_RATIO = 200


def project_zip(content: bytes) -> tuple[Ri223RarMember, ...]:
    """Only stored/deflated ordinary documents, complete preflight, bounded reads."""
    if not 0 < len(content) <= MAX_MEMBER_BYTES or not content.startswith(b'PK\x03\x04'):
        raise ValueError('ZIP signature or compressed size outside budget')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as bundle:
            infos = bundle.infolist()
            if not 0 < len(infos) <= MAX_ZIP_ENTRIES:
                raise ValueError('ZIP entry count outside budget')
            seen = set()
            files = set()
            total = 0
            accepted = []
            for info in infos:
                name = info.orig_filename
                path = name[:-1] if info.is_dir() else name
                parts = path.split('/')
                mode = stat.S_IFMT(info.external_attr >> 16)
                if (not path or len(path) > 1024 or len(parts) > 8
                        or any(x in ('', '.', '..') or len(x) > 260 for x in parts)
                        or any(c in name for c in ('\\', ':', '*', '?', '[', ']', '\ufffd'))
                        or any(ord(c) < 32 for c in name)
                        or name != info.filename or path in seen
                        or info.flag_bits & (1 | 0x40 | 0x2000)
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise ValueError('Unsafe or unsupported ZIP entry')
                seen.add(path)
                if info.is_dir():
                    if mode not in (0, stat.S_IFDIR) or info.file_size != 0:
                        raise ValueError('Invalid ZIP directory')
                    continue
                if mode not in (0, stat.S_IFREG) or info.external_attr & 0x10:
                    raise ValueError('ZIP links and special files forbidden')
                if (PurePosixPath(path).suffix.lower() not in PROCESSABLE_MEMBERS
                        or not 0 < info.file_size <= MAX_MEMBER_BYTES
                        or not 0 < info.compress_size <= len(content)
                        or info.file_size > info.compress_size * MAX_ZIP_RATIO):
                    raise ValueError('ZIP member outside format/size/ratio budget')
                files.add(path)
                total += info.file_size
                accepted.append(info)
            # Reject file/directory collisions, including implicit directories.
            if any('/'.join(path.split('/')[:i]) in files
                   for path in seen for i in range(1,len(path.split('/')))):
                raise ValueError('ZIP path collision')
            if (not 0 < len(accepted) <= MAX_MEMBERS or total > MAX_EXPANDED_BYTES
                    or total > len(content) * MAX_ZIP_RATIO):
                raise ValueError('ZIP expanded budget exceeded')
            result = []
            for info in accepted:
                with bundle.open(info) as stream:
                    raw = stream.read(info.file_size + 1)
                if len(raw) != info.file_size:
                    raise ValueError('ZIP member size mismatch')
                # Ordinary documents may be OOXML ZIP packages, but never
                # recursively expand generic archive members.
                result.append(Ri223RarMember(info.filename,PurePosixPath(info.filename).name,raw))
            return tuple(result)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise ValueError('ZIP integrity or decompression failure') from exc


# Only one immutable successful projection per synchronous dossier. The cache
# key contains exact bytes, not file name, mtime, supplied hash or metadata.
# Every caller still reads and verifies its current original before this call.
_projection_scope: ContextVar[list | None] = ContextVar("ri223_projection_scope", default=None)


@contextmanager
def container_projection_scope():
    cache = []
    token = _projection_scope.set(cache)
    try:
        yield
    finally:
        cache.clear()
        _projection_scope.reset(token)


def project_container(content: bytes, extension: str):
    cache = _projection_scope.get()
    if cache is not None and type(content) is bytes:
        if cache and cache[0] == extension and cache[1] == content:
            return cache[2]
        result = tuple(_project_container(content, extension))
        # Replace rather than accumulate: one parent, existing size limits.
        cache[:] = [extension, content, result]
        return result
    return _project_container(content, extension)


def _project_container(content: bytes, extension: str):
    if extension == '.rar':
        return project_rar(content)
    if extension == '.zip':
        return project_zip(content)
    raise ValueError('Unsupported container')
