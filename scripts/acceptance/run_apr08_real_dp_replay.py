"""Replay one saved real archive through a disposable authenticated DP HTTP process."""
from __future__ import annotations

import hashlib
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

DP = Path('/Volumes/ArvectumSSD/Arvectum/repos/data-platform')
RUNS = Path('/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr04-owner-onboarding-20261015/runs')
RUN = 'toa-run-20261012200402-7249ed'


def inventory(root: Path) -> dict[str, str]:
    members = list(root.rglob('*'))
    if not root.is_dir() or root.is_symlink() or len(members) > 128 or any(p.is_symlink() for p in members):
        raise ValueError('Unsafe saved archive tree')
    files = [p for p in members if p.is_file()]
    if not files or sum(p.stat().st_size for p in files) > 50_000_000:
        raise ValueError('Archive inventory outside replay budget')
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main() -> int:
    root = RUNS / RUN
    before = inventory(root)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    key = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix='apr08-dp-private-') as tmp:
        # Isolated process: no inherited real service configuration or DB.
        env = {k: v for k, v in os.environ.items() if not k.startswith(('ARVECTUM_DATA_', 'AI_CORP_'))
               and k.upper() not in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY')}
        env.update(PYTHONPATH=str(DP / 'src'), ARVECTUM_DATA_DEPLOYMENT_MODE='local-private',
                   ARVECTUM_DATA_INTERNAL_API_KEY=key, ARVECTUM_DATA_DATABASE_URL='',
                   ARVECTUM_DATA_EMBEDDING_PROVIDER='hashing', ARVECTUM_DATA_CROSS_ENCODER_PROVIDER='disabled',
                   ARVECTUM_DATA_REASONING_POLICY='disabled', ARVECTUM_DATA_VISION_POLICY='disabled',
                   ARVECTUM_DATA_OCR_PROVIDER='disabled', ARVECTUM_DATA_LOG_LEVEL='WARNING')
        with (Path(tmp) / 'dp.log').open('wb') as log:
            proc = subprocess.Popen([str(DP / '.venv/bin/python'), '-m', 'uvicorn',
                                     'arvectum_data.api.app:create_app', '--factory', '--host', '127.0.0.1',
                                     '--port', str(port), '--no-access-log'], cwd=tmp, env=env, stdout=log, stderr=log)
            try:
                for _ in range(50):
                    if proc.poll() is not None:
                        raise RuntimeError('Isolated DP startup failed')
                    try:
                        if httpx.get(base + '/health', timeout=.3, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('Isolated DP not ready')
                assert httpx.post(base + '/v1/process/document', timeout=3, trust_env=False).status_code == 401
                os.environ.update(AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR=str(RUNS),
                                  AI_CORP_RAG_DATA_PLATFORM_BASE_URL=base, AI_CORP_RAG_DATA_PLATFORM_API_KEY=key,
                                  AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS='12')
                from src.modules.tender_operator_agent_demo.evidence_document_search import (
                    DocumentSearchQuestion,
                    search_run_documents,
                )
                from src.shared.config.settings import get_settings

                get_settings.cache_clear()
                result = search_run_documents(RUN, DocumentSearchQuestion(query='оплата работ'))
                assert result['status'] == 'VERIFIED_EXCERPTS_ONLY' and result['citations']
                assert result['verification_attempts'] <= 2 and not result['bid_ready'] and not result['scope_complete']
                for cite in result['citations']:
                    assert cite['original_sha256'] in before.values()
                assert inventory(root) == before
                print('APR08_REAL_DP_REPLAY_PASS', 'citations', len(result['citations']),
                      'attempts', result['verification_attempts'], 'anonymous_401', True, 'originals_unchanged', True)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
    print('APR08_ISOLATED_DP_REMOVED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
