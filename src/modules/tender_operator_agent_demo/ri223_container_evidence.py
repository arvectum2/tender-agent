"""Opt-in, receipt-bound RAR projection; never unpack to archive-supplied paths."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from src.tender_research.providers.ri223_rar_members import extract_ri223_rar_members

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


def member_receipt(parent_sha: str, member) -> dict:
    return {'parent_sha256': parent_sha, 'member_path': member.path,
            'member_sha256': hashlib.sha256(member.content).hexdigest(),
            'member_bytes': len(member.content), 'container_format': 'RAR'}
