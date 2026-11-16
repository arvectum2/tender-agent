"""Explicit isolated operator pilot, not a scheduled production collector."""
from __future__ import annotations

import argparse
import json
import resource
import signal
from pathlib import Path

from scripts.research.commercial_document_acquisition import (
    MAX_ARCHIVE,
    download_b2b,
    observe,
    route_permitted,
)
from src.modules.saas_foundation.commercial_sources import commercial_identity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card',required=True)
    parser.add_argument('--storage-state',type=Path)
    parser.add_argument('--download-dir',type=Path)
    parser.add_argument('--confirm-authorized-download',action='store_true')
    parser.add_argument('--operator-consent-reference',help='Reference to written B2B-Center permission for this automated access; required even for public probes')
    args=parser.parse_args()
    platform,_=commercial_identity(args.card)
    if platform=='b2bcenter' and not (args.operator_consent_reference or '').strip():
        parser.error('B2B-Center regulation 5.4 requires written operator consent before automated access')
    download=bool(args.download_dir)
    if download and (platform!='b2bcenter' or not args.confirm_authorized_download or not args.storage_state):
        parser.error('B2B download requires explicit authorization and an authorized session')
    if args.storage_state and not download:parser.error('Public probes do not consume account sessions')
    state=None; destination=None
    if download:
        p=args.storage_state
        if not p.is_file() or p.is_symlink() or p.stat().st_mode&0o077 or p.stat().st_size>1024*1024:
            parser.error('Private regular state file required')
        state=json.loads(p.read_text())
        # Never reuse other sites' credentials or arbitrary local storage origins.
        if any(x.get('domain') not in {'www.b2b-center.ru','.b2b-center.ru','b2b-center.ru'} for x in state.get('cookies',[])) or any(x.get('origin')!='https://www.b2b-center.ru' for x in state.get('origins',[])):
            parser.error('Dedicated B2B-only session required')
        args.download_dir.mkdir(mode=0o700,parents=False,exist_ok=False)
        destination=args.download_dir/'documentation.zip'
    from playwright.sync_api import sync_playwright
    # Limit file output and failed browser operations. Use a disposable browser, never a shared profile.
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_ARCHIVE,MAX_ARCHIVE))
    signal.alarm(65)
    try:
        with sync_playwright() as driver:
            browser=driver.chromium.launch(channel='chrome',headless=True,timeout=8000)
            try:
                context=browser.new_context(storage_state=state,accept_downloads=download,service_workers='block',ignore_https_errors=False)
                context.route('**/*',lambda r:r.continue_() if route_permitted(args.card,r.request.url,r.request.method,r.request.resource_type) else r.abort())
                page=context.new_page()
                response=page.goto(args.card,wait_until='domcontentloaded',timeout=12000)
                if not response or response.status!=200 or page.url!=args.card:
                    raise ValueError('Exact successful card navigation required')
                result=observe(page,args.card,authenticated=bool(state));result['http_status']=response.status
                if download and result['state']=='B2B_DOCUMENTED_UI_READY':
                    result['archive']=download_b2b(page,args.card,destination,authorized=args.confirm_authorized_download)
                    result['state']='ARCHIVE_CAPTURED_REVIEW_REQUIRED'
                    # Do not claim full document coverage or verified qualification.
                print(json.dumps(result,ensure_ascii=False))
            finally:browser.close()
    except Exception as exc:  # noqa: BLE001 -- boundary, never leak session details
        # Playwright exceptions may embed sensitive URL parameters; print only class.
        print(json.dumps({'state':'ACQUISITION_FAILED','error_type':type(exc).__name__}));return 1
    finally:signal.alarm(0)
    return 0


if __name__=='__main__':raise SystemExit(main())
