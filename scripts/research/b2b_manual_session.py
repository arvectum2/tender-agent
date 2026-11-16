"""Local interactive Arvectum sign-in only; no automated platform navigation.

Run in a local user terminal when ready to sign in to the dedicated Chrome window.
The user enters credentials/2FA directly there. Never run unattended. Never send
passwords, codes, cookies or the resulting file into chat or source control.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from scripts.research.b2b_network_guard import GuardError
from scripts.research.b2b_session_policy import HOST, MAX_STATE, cookie_jar


def select_cookie_state(cookies):
    if not isinstance(cookies,list):raise GuardError('Invalid browser cookie metadata')
    domains={HOST,'b2b-center.ru','.b2b-center.ru','.'+HOST}
    state={'cookies':[c for c in cookies if isinstance(c,dict) and c.get('domain') in domains and c.get('secure') is True],'origins':[]}
    cookie_jar(state)
    return state


def save_private(path,state):
    path=Path(path);directory=path.parent;info=directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise GuardError('Private owner-only directory required')
    cookie_jar(state);raw=json.dumps(state,ensure_ascii=True,separators=(',',':')).encode()
    if not 0<len(raw)<=MAX_STATE:raise GuardError('Session size limit')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    except BaseException:
        path.unlink(missing_ok=True);raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',type=Path,required=True);args=parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():parser.error('Interactive local terminal required')
    if args.session.exists() or args.session.is_symlink():parser.error('Choose a new private session file; no overwrite')
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as driver:
            browser=driver.chromium.launch(channel='chrome',headless=False,timeout=8000);context=browser.new_context(service_workers='block',ignore_https_errors=False)
            try:
                context.new_page()
                print('Вручную откройте https://www.b2b-center.ru/ в новом окне Chrome и войдите в личный кабинет ООО «Арвектум».')
                print('Не вводите пароль или код в терминал. После проверки организации в кабинете введите ARVECTUM здесь для сохранения отдельной сессии.')
                if input('Подтверждение (ARVECTUM): ').strip()!='ARVECTUM':raise GuardError('Manual confirmation absent')
                state=select_cookie_state(context.cookies());save_private(args.session,state)
                print('Локальная cookie-сессия сохранена. Принадлежность организации автоматически не проверена; живой агент не включён.')
            finally:context.close();browser.close()
    except Exception as exc:  # noqa: BLE001 -- do not leak data in browser exceptions
        print('Session not accepted: '+type(exc).__name__);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
