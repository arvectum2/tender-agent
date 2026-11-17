"""Read-only local CLI; expected manifest digest must come from trusted review."""
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from xml.etree.ElementTree import ParseError

from src.tender_research.reviewed_contract_evidence import (
    MAX_MANIFEST,
    MAX_SOURCE,
    intake,
    load_manifest,
)


def read_regular(path:Path,limit:int)->bytes:
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        meta=os.fstat(f.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 0<meta.st_size<=limit:
            raise ValueError('Invalid local input file')
        raw=f.read(limit+1)
        if not 0<len(raw)<=limit:raise ValueError('Input size limit exceeded')
        return raw


def run(manifest_path:Path,pin:str,source_dir:Path):
    raw=read_regular(manifest_path,MAX_MANIFEST)
    bundle=load_manifest(raw,pin)
    originals={r.source_sha256:read_regular(source_dir/(r.source_sha256+'.xml'),MAX_SOURCE) for r in bundle.records}
    return intake(raw,expected_manifest_sha256=pin,originals=originals)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--reviewed-sha256',required=True)
    p.add_argument('--originals',type=Path,required=True)
    args=p.parse_args()
    try:
        result=run(args.manifest,args.reviewed_sha256,args.originals)
    except (ValueError, OSError, ParseError, RecursionError) as e:
        p.exit(2,'Evidence rejected: '+type(e).__name__+'\n')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=='__main__':
    main()
