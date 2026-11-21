"""Offline development acceptance for APR08, not production/legal release.

Requires the existing private source corpus, archived runs, DP checkout and Chromium.
Runs each replay in a fresh subprocess, requires its positive markers and checks
all versioned legal-source bytes before/after. Screenshots remain in a private dir.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from src.modules.tender_operator_agent_demo.evidence_amendment_timing import (
    SOURCES as AMENDMENT_SOURCES,
)
from src.modules.tender_operator_agent_demo.evidence_government_copies import (
    PDF_PROJECTION_SHA,
)
from src.modules.tender_operator_agent_demo.evidence_government_copies import (
    SOURCES as GOVERNMENT_SOURCES,
)
from src.modules.tender_operator_agent_demo.evidence_statute_corpus import SNAPSHOTS

DP = Path('/Volumes/ArvectumSSD/Arvectum/repos/data-platform')
DP_HEAD = '38322fd5f1cbec2d377c478d9980cae2382366a0'


def source_receipts() -> dict[str, str]:
    receipts = {s.filename: s.sha256 for s in SNAPSHOTS}
    receipts.update({s[0]: s[1] for s in AMENDMENT_SOURCES})
    receipts.update({s[0]: s[1] for s in GOVERNMENT_SOURCES.values()})
    receipts['223fz-mchs-blocks.json'] = PDF_PROJECTION_SHA
    return receipts


def check_sources(directory: Path) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError('Unsafe private corpus directory')
    for name, expected in source_receipts().items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 3_000_000:
            raise RuntimeError(f'Unsafe or missing source: {name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Pinned source mismatch: {name}')


def main() -> int:
    source_dir = Path(os.environ['AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR'])
    screenshots = Path(os.environ['APR08_SCREENSHOT_DIR'])
    if screenshots.is_symlink() or not screenshots.is_dir() or any(screenshots.iterdir()):
        raise RuntimeError('Use an empty private screenshot directory')
    check_sources(source_dir)
    if subprocess.check_output(['git','-C',str(DP),'rev-parse','HEAD'], text=True).strip() != DP_HEAD:
        raise RuntimeError('DP reference revision changed; review the new revision first')
    if subprocess.check_output(['git','-C',str(DP),'status','--porcelain','--untracked-files=no'], text=True).strip():
        raise RuntimeError('DP tracked files are dirty')
    allowed = ('HOME','PATH','TMPDIR','LANG','LC_ALL','APR08_PLAYWRIGHT_MODULE','APR08_CHROME','APR08_NODE')
    env = {k:v for k,v in os.environ.items() if k in allowed}
    env.update(AI_CORP_TENDER_LEGAL_SNAPSHOTS_DIR=str(source_dir), APR08_COMPOSED_BROWSER='1',
               APR08_STATUTE_BROWSER_ACCEPTANCE='1', APR08_AMENDMENT_BROWSER_ACCEPTANCE='1',
               APR08_GOVERNMENT_COPIES_BROWSER='1')
    scenarios = [
        ('run_apr08_government_copies_replay', {}, ['APR08_GOVERNMENT_COPIES_REPLAY_PASS']),
        ('run_apr08_security_archive_replay', {'APR08_PINNED_BROWSER_ACCEPTANCE':'1'},
         ['APR08_COMPOSED_PINNED_BROWSER_PASS','APR08_PINNED_XML_CHROMIUM_PASS','APR08_STATUTE_BROWSER_PASS',
          'APR08_GOVERNMENT_COPIES_BROWSER_PASS','APR08_AMENDMENT_BROWSER_PASS','APR08_SECURITY_ARCHIVE_REPLAY_PASS']),
        ('run_apr08_security_archive_replay', {'APR08_PINNED_BROWSER_ACCEPTANCE':'1','APR08_BROWSER_NARROW':'1'},
         ['APR08_COMPOSED_PINNED_BROWSER_PASS','APR08_PINNED_XML_CHROMIUM_PASS','APR08_SECURITY_ARCHIVE_REPLAY_PASS']),
        ('run_apr08_real_dp_replay', {'APR08_BROWSER_ACCEPTANCE':'1'},
         ['APR08_COMPOSED_DP_BROWSER_PASS','APR08_REAL_CHROMIUM_PASS','APR08_REAL_DP_REPLAY_PASS','APR08_ISOLATED_DP_REMOVED']),
    ]
    for index,(module, extra, markers) in enumerate(scenarios):
        target = screenshots / f'{index+1:02d}-{module}'
        target.mkdir(mode=0o700)
        checked = subprocess.run([sys.executable,'-m','scripts.acceptance.'+module],
                                 env={**env,**extra,'APR08_SCREENSHOT_DIR':str(target)},
                                 capture_output=True,text=True,timeout=100,check=False)
        (target/'replay.log').write_text(checked.stdout+'\n'+checked.stderr)
        if checked.returncode or not all(marker in checked.stdout for marker in markers):
            raise RuntimeError(f'Acceptance failed: {module} scenario {index+1}; see private replay.log')
        for line in checked.stdout.splitlines():
            if any(marker in line for marker in markers):
                print(line,flush=True)
    check_sources(source_dir)
    print(f'APR08_INTEGRATED_DEVELOPMENT_PASS {len(scenarios)} scenarios; {len(source_receipts())} pinned legal source files unchanged',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
