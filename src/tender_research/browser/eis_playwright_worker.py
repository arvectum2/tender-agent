"""Isolated, opt-in browser transport for public EIS search only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

_MAX_BYTES = 5 * 1024 * 1024
_SEARCH_PATH = '/epz/order/extendedsearch/results.html'


def _public_origin(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return (parts.scheme == 'https' and parts.hostname == 'zakupki.gov.ru'
                and parts.port in (None, 443) and parts.username is None and parts.password is None)
    except ValueError:
        return False


def is_eis_search_url(url: str) -> bool:
    if not _public_origin(url):
        return False
    parts = urlsplit(url)
    return parts.path == _SEARCH_PATH and bool(parts.query) and not parts.fragment


def _same_search(requested: str, actual: str) -> bool:
    return (is_eis_search_url(actual)
            and sorted(parse_qsl(urlsplit(requested).query, keep_blank_values=True))
            == sorted(parse_qsl(urlsplit(actual).query, keep_blank_values=True)))


def browser_fetch(url: str) -> dict:
    if not is_eis_search_url(url):
        return {'status': 'denied_url'}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright, playwright.chromium.launch(
            channel='chrome', headless=True, args=['--no-proxy-server']
        ) as browser:
            context = browser.new_context(accept_downloads=False, service_workers='block')
            context.route('**/*', lambda route: route.continue_() if (
                _public_origin(route.request.url)
                and route.request.method in ('GET', 'HEAD')
                and route.request.resource_type not in ('image', 'font', 'media')
                and (not route.request.is_navigation_request() or _same_search(url, route.request.url))
            ) else route.abort())
            page = context.new_page()
            response = page.goto(url, wait_until='domcontentloaded', timeout=18000)
            if response is None or response.status != 200:
                return {'status': 'http_unavailable'}
            if not _same_search(url, page.url):
                return {'status': 'unexpected_navigation'}
            html = page.content()
            if len(html.encode('utf-8')) > _MAX_BYTES:
                return {'status': 'oversize'}
            return {'status': 'ok', 'html': html}
    except ImportError:
        return {'status': 'playwright_missing'}
    except Exception:  # noqa: BLE001 - isolate browser failures; no request details in diagnostics
        return {'status': 'browser_error'}


def fetch_eis_browser(url: str, python_executable: str) -> dict:
    if not is_eis_search_url(url):
        return {'status': 'denied_url'}
    interpreter = Path(python_executable)
    if not interpreter.is_absolute() or not interpreter.is_file():
        return {'status': 'worker_unavailable'}
    env = {key: os.environ[key] for key in ('HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL') if key in os.environ}
    try:
        result = subprocess.run(
            [str(interpreter), '-I', str(Path(__file__).resolve()), url],
            capture_output=True, text=True, timeout=30, env=env, check=False,
        )
        if result.returncode or len(result.stdout) > _MAX_BYTES * 6:
            return {'status': 'worker_failed'}
        data = json.loads(result.stdout)
        if not isinstance(data, dict) or data.get('status') != 'ok':
            return {'status': 'browser_unavailable'}
        html = data.get('html')
        if not isinstance(html, str) or len(html.encode('utf-8')) > _MAX_BYTES:
            return {'status': 'invalid_worker_response'}
        return {'status': 'ok', 'html': html}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'worker_unavailable'}


if __name__ == '__main__':
    result = browser_fetch(sys.argv[1]) if len(sys.argv) == 2 else {'status': 'invalid_input'}
    print(json.dumps(result, ensure_ascii=False))
