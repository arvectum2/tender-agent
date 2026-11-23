"""Local interactive Arvectum sign-in only; no automated platform navigation.

Run in a local user terminal when ready to sign in to the dedicated Chrome window.
The user authenticates manually in a dedicated persistent Chrome profile.
Password mode is the default; optional EDS mode remains supported. Never inspect or copy
private signing keys, PINs, existing browser profiles or credential databases.
Never send session secrets or the resulting file into chat or source control.
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



def dedicated_profile(path):
    """Require a new or previously marked dedicated local profile, not everyday Chrome."""
    path=Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink():raise GuardError('Absolute dedicated profile path required')
    parent=path.parent;info=parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise GuardError('Private owner-only profile parent required')
    marker=path/'.tender-agent-b2b-eds-profile'
    if not path.exists():
        path.mkdir(mode=0o700)
        fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:f.write('dedicated-b2b-eds-v1\n')
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise GuardError('Private profile required')
    fd=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'r') as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1 or f.read(100)!='dedicated-b2b-eds-v1\n':raise GuardError('Not a dedicated B2B profile')
    return path


def session_summary(context):
    # Metadata only. Never enumerate or print storage keys/values or token contents.
    pages=[p for p in context.pages if p.url.startswith('https://'+HOST+'/')]
    return {'b2b_page_open':bool(pages),'cookie_count':len(select_cookie_state(context.cookies())['cookies'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True,help='Dedicated owner-only persistent Chrome profile')
    parser.add_argument('--auth-method',choices=('password','eds'),default='password')
    args=parser.parse_args()
    if sys.platform!='darwin' or not sys.stdin.isatty() or not sys.stdout.isatty():parser.error('Interactive local macOS terminal required')
    if args.session.exists() or args.session.is_symlink():parser.error('Choose a new private session file; no overwrite')
    from playwright.sync_api import sync_playwright
    try:
        profile=dedicated_profile(args.profile)
        with sync_playwright() as driver:
            options={'channel':'chrome','headless':False,'timeout':8000,'ignore_https_errors':False,'chromium_sandbox':True}
            if args.auth_method=='eds':options['ignore_default_args']=['--disable-extensions']
            context=driver.chromium.launch_persistent_context(str(profile),**options)
            try:
                print('Используйте только открывшийся выделенный профиль Chrome.')
                if args.auth_method=='eds':
                    print('При необходимости установите официальное расширение криптопровайдера вручную. Войдите через ЭЦП; закрытый ключ и PIN не передаются агенту.')
                else:
                    print('Войдите вручную с логином и паролем в браузере. Не вводите их в терминал или чат; не сохраняйте пароль в браузере.')
                print('Адрес для ручного входа: https://www.b2b-center.ru/')
                print('Проверьте, что открыт личный кабинет ООО «Арвектум». Затем введите ARVECTUM в этом терминале.')
                if input('Подтверждение (ARVECTUM): ').strip()!='ARVECTUM':raise GuardError('Manual confirmation absent')
                summary=session_summary(context)
                if not summary['b2b_page_open']:raise GuardError('Exact B2B HTTPS page required')
                state=select_cookie_state(context.cookies());save_private(args.session,state)
                print(json.dumps({'state':'LOCAL_SESSION_SAVED','auth_method':args.auth_method,'cookie_count':summary['cookie_count'],'account_identity_verified':False,'cross_device_portability_verified':False,'live_agent_enabled':False},ensure_ascii=False))
            finally:context.close()
    except Exception as exc:  # noqa: BLE001 -- do not leak data in browser exceptions
        print('Session not accepted: '+type(exc).__name__);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
