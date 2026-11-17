"""Prepare candidate release bytes on stdout; NEVER publish or change trusted pins."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree.ElementTree import ParseError

from scripts.price01.intake_reviewed_contracts import read_regular
from src.tender_research.reviewed_contract_evidence import (
    MAX_MANIFEST,
    MAX_SOURCE,
    load_manifest,
)
from src.tender_research.reviewed_contract_registry import (
    MAX_RELEASE,
    append_candidate,
    load_release,
    publication_group,
)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',type=Path,required=True)
    p.add_argument('--release-sha256',required=True)
    p.add_argument('--action',choices=['PUBLISH','WITHDRAW'],required=True)
    p.add_argument('--group-id',required=True)
    p.add_argument('--reason',required=True)
    p.add_argument('--manifest',type=Path)
    p.add_argument('--reviewed-sha256')
    p.add_argument('--originals',type=Path)
    a=p.parse_args()
    try:
        old=load_release(read_regular(a.release,MAX_RELEASE),a.release_sha256)
        group=None
        if a.action=='PUBLISH':
            if not all((a.manifest,a.reviewed_sha256,a.originals)):raise ValueError('Reviewed original inputs required')
            manifest=read_regular(a.manifest,MAX_MANIFEST)
            bundle=load_manifest(manifest,a.reviewed_sha256)
            originals={r.source_sha256:read_regular(a.originals/(r.source_sha256+'.xml'),MAX_SOURCE) for r in bundle.records}
            group=publication_group(manifest,a.reviewed_sha256,originals,a.group_id)
        elif any((a.manifest,a.reviewed_sha256,a.originals)):
            raise ValueError('Withdrawal has no new manifest')
        raw=append_candidate(old,action=a.action,group_id=a.group_id,reason=a.reason,group=group)
    except (ValueError,OSError,ParseError,RecursionError) as e:
        p.exit(2,'Candidate rejected: '+type(e).__name__+'\n')
    sys.stdout.buffer.write(raw)


if __name__=='__main__':
    main()
