"""Local CLI for previously verified RI223 archives; never fetches or analyses."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from tempfile import TemporaryDirectory

from src.modules.tender_operator_agent_demo.evidence_ri223_archive import (
    SOURCE,
    ri223_archive_observation,
    trusted_pins,
)
from src.tender_research.providers.ri223_soap_evidence import (
    MAX_ARCHIVE_BYTES,
    parse_ri223_archive,
)


def import_archive(root: Path, archive: Path, number: str, *, attachments: list[Path] | None = None, processor=None, expand_rar: bool = False) -> str:
    if expand_rar and attachments is None:
        raise ValueError('RAR expansion requires verified original attachments')
    if not root.is_absolute() or root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        raise ValueError('Explicit private existing runs directory (0700) required')
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Unsafe source archive')
    pin=trusted_pins().get(number)
    if pin is None:
        raise ValueError('Missing trusted RI223 receipt')
    with archive.open('rb') as f:
        data=f.read(MAX_ARCHIVE_BYTES+1)
    if not 0<len(data)<=MAX_ARCHIVE_BYTES or hashlib.sha256(data).hexdigest()!=pin[0]:
        raise ValueError('Unverified RI223 archive')
    now=datetime.now(UTC)
    run_id=f"toa-run-{now.strftime('%Y%m%d%H%M%S')}-{token_hex(3)}"
    target=root/run_id
    with TemporaryDirectory(dir=root,prefix='.ri223-staging-') as tmp:
        stage=Path(tmp)
        directory=stage/'input';directory.mkdir(mode=0o700)
        saved=directory/'ri223.zip';saved.write_bytes(data)
        parsed=parse_ri223_archive(saved,number)
        proof=parsed.raw_payload['evidence'];member=proof['xml_member']
        if (proof['archive_sha256'],proof['xml_sha256'],parsed.raw_payload['notice_version'])!=pin:
            raise ValueError('Unverified selected RI223 revision')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.xml',member):
            raise ValueError('Unsafe selected member')
        with zipfile.ZipFile(saved) as bundle:
            raw=bundle.read(member)
        (directory/member).write_bytes(raw)
        meta={'run_id':run_id,'procurement_id':number,'procurement_notice_number':number,'procurement_source':SOURCE,
              'procurement_law':'223-ФЗ','archive_stored_name':saved.name,'files':[{'file_id':'FILE-01','original_name':member,
              'display_name':member,'stored_name':member,'extension':'.xml','size_bytes':len(raw),'content_type':'application/xml','source':'ri223_archive'}],
              'created_at':now.isoformat(),'mode':'procurement_search_intake','tender_title':parsed.title,
              'tender_category':'Архив RI223','customer_name':'UNKNOWN','status':'needs_review','analysis_mode':'archived_evidence_only',
              'archive_downloaded':False,'attachments_status':'not_imported','human_in_the_loop':True,
              'warnings':[],'limitations':['Только архивное XML. Вложения не импортированы; полный анализ недоступен.']}
        if ri223_archive_observation(stage,meta)['status']!='PINNED_RI223_ARCHIVED_NOTICE':
            raise ValueError('Source verification failed')
        if attachments is not None:
            from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import (
                import_attachments,
            )
            from src.shared.document_processing import process_document_bytes

            import_attachments(stage,meta,attachments,processor or process_document_bytes,expand_rar=expand_rar)
        (stage/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
        target.mkdir(mode=0o700,exist_ok=False)
        try:
            (stage/'input').rename(target/'input')
            if (stage/'normalized').exists():
                (stage/'normalized').rename(target/'normalized')
            (stage/'metadata.json').rename(target/'metadata.json')
        except BaseException:
            shutil.rmtree(target)
            raise
    return run_id


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--number',required=True)
    parser.add_argument('--attachment',type=Path,action='append',help='One local original per unique trusted receipt digest')
    parser.add_argument('--expand-rar',action='store_true',help='Opt-in bounded RAR member projection')
    args=parser.parse_args()
    root=os.environ.get('AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR')
    if not root:
        parser.error('Explicit private runs directory required')
    print(import_archive(Path(root),args.archive,args.number,attachments=args.attachment,expand_rar=args.expand_rar))


if __name__=='__main__':
    main()
