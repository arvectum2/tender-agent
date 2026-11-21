"""Replay pinned RI223 original attachments through disposable DP HTTP."""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

DP = Path('/Volumes/ArvectumSSD/Arvectum/repos/data-platform')


def main() -> int:
    assert subprocess.check_output(["git","-C",str(DP),"rev-parse","HEAD"],text=True).strip()=="38322fd5f1cbec2d377c478d9980cae2382366a0"
    assert not subprocess.check_output(["git","-C",str(DP),"status","--porcelain","--untracked-files=no"],text=True).strip()
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
                runs=Path(tmp)/'runs';runs.mkdir(mode=0o700)
                os.environ.update(AI_CORP_RAG_DATA_PLATFORM_BASE_URL=base,AI_CORP_RAG_DATA_PLATFORM_API_KEY=key,AI_CORP_RAG_DATA_PLATFORM_TIMEOUT_SECONDS='12')
                from scripts.acceptance.apr03b_ri223_attachment_cases import replay

                replay(runs)
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
