"""Real browser over the actual isolated operator ASGI application, read-only allowlist."""
from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from starlette.responses import Response


def run_browser(app, run: str, password: str, screenshot_dir: Path, *, scenario: str = 'documents') -> None:
    prefix = '/api/demo/tender-agent'
    workspace = '/pilot/tender-agent/workspace'
    allowed_get = {workspace, workspace+'/assets/workspace.css', workspace+'/assets/workspace.js',
                   f'{prefix}/runs/{run}', f'{prefix}/runs/{run}/events', f'{prefix}/runs/{run}/report',
                   f'{prefix}/workspace/runs/{run}/evidence'}
    allowed_post = {f'{prefix}/workspace/runs/{run}/evidence-{part}' for part in ('answer','search','question')}
    allowed_post.add(prefix+'/workspace/price-scenario/calculate')
    async def restricted(scope, receive, send):
        if scope['type'] != 'http' or scope['path'] not in (allowed_get if scope['method']=='GET' else allowed_post if scope['method']=='POST' else set()):
            await Response(status_code=403)(scope, receive, send)
            return
        await app(scope, receive, send)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    server=uvicorn.Server(uvicorn.Config(restricted, host='127.0.0.1', port=port, log_level='warning', access_log=False, lifespan='off'))
    thread=threading.Thread(target=server.run, daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        else:raise RuntimeError('isolated operator server not ready')
        assert httpx.get(origin+workspace,trust_env=False).status_code==401
        assert httpx.post(origin+prefix+f'/runs/{run}/analyze',trust_env=False).status_code==403
        env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL','APR08_PLAYWRIGHT_MODULE','APR08_CHROME','APR08_BROWSER_NARROW','APR08_STATUTE_BROWSER_ACCEPTANCE','APR08_AMENDMENT_BROWSER_ACCEPTANCE','APR08_GOVERNMENT_COPIES_BROWSER','APR08_COMPOSED_BROWSER')}
        env.update(APR08_BROWSER_ORIGIN=origin,APR08_BROWSER_RUN=run,APR08_BROWSER_PASSWORD=password,APR08_SCREENSHOT_DIR=str(screenshot_dir),APR08_BROWSER_SCENARIO=scenario)
        subprocess.run([os.environ['APR08_NODE'],str(Path(__file__).with_name('run_apr08_browser.cjs'))],env=env,check=True,timeout=60)
    finally:
        server.should_exit=True;thread.join(timeout=10)
        if thread.is_alive():raise RuntimeError('operator server failed to stop')
