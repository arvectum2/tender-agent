"""Offline-testable, persistent single-egress HTTP admission gate.

One private canonical state directory for ALL agent workers sharing the designated
IP. No live browser integration is authorized by this module alone. Reservations
are durable before dispatch; hold the process lock through the bounded operation.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

WINDOW = 60_000_000_000
LIMIT = 60


class GuardError(RuntimeError):
    pass


class WaitRequired(GuardError):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f'HTTP admission deferred for {seconds:.3f} seconds')


def boot_identity():
    if sys.platform == 'darwin':
        return subprocess.check_output(['/usr/sbin/sysctl','-n','kern.bootsessionuuid'],text=True,timeout=3).strip()
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


class EgressGate:
    def __init__(self, directory, *, clock=time.monotonic_ns, boot=None):
        self.directory=Path(directory);self.clock=clock;self.boot=boot or boot_identity()
        info=self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or not self.boot:
            raise GuardError('Private canonical egress directory required')
        self.state=self.directory/'egress.json';self.lock=self.directory/'egress.lock'

    @staticmethod
    def _private(fd):
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1:
            raise GuardError('Invalid private egress state')

    @contextmanager
    def _locked(self):
        fd=os.open(self.lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            self._private(fd);fcntl.flock(fd,fcntl.LOCK_EX);yield
        finally:os.close(fd)

    def _write(self,s):
        fd,path=tempfile.mkstemp(prefix='.egress-',dir=self.directory)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(s,f,separators=(',',':'),allow_nan=False);f.flush();os.fsync(f.fileno())
            os.replace(path,self.state)
            d=os.open(self.directory,os.O_RDONLY)
            try:os.fsync(d)
            finally:os.close(d)
        finally:
            if os.path.exists(path):os.unlink(path)

    def initialize(self):
        """Explicit one-time provisioning; no resetting a missing/corrupt live state."""
        with self._locked():
            if self.state.exists() or self.state.is_symlink():raise GuardError('Egress state already exists')
            now=self.clock();self._write({'schema':1,'boot':self.boot,'last_ns':now,'events':[],'pending':False,'blocked_until':now+WINDOW,'receipts':[]})

    def _read(self):
        fd=os.open(self.state,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'r') as f:
            self._private(f.fileno());raw=f.read(128*1024+1)
        try:
            s=json.loads(raw)
            if len(raw)>128*1024 or s['schema']!=1 or not isinstance(s['boot'],str) or type(s['pending']) is not bool or any(type(s[k]) is not int or s[k]<0 for k in ('last_ns','blocked_until')):raise ValueError
            if not isinstance(s['events'],list) or len(s['events'])>LIMIT or s['events']!=sorted(s['events']) or any(type(x) is not int or not 0<=x<=s['last_ns'] for x in s['events']):raise ValueError
            if not isinstance(s['receipts'],list) or len(s['receipts'])>200:raise ValueError
        except (ValueError,TypeError,KeyError) as exc:raise GuardError('Corrupt egress state; fail closed') from exc
        return s

    def _recover(self,s,now):
        if s['boot']!=self.boot or now<s['last_ns'] or s['pending']:
            # Crash may occur after dispatch but before the completion reservation;
            # never erase the prior server cooldown when changing clock epochs.
            remaining=max(0,s['blocked_until']-s['last_ns'])
            s.update(boot=self.boot,last_ns=now,events=[],pending=False,blocked_until=now+max(WINDOW,remaining))
            self._write(s)

    def dispatch(self,operation,*,method):
        """Call exactly one bounded HTTP attempt. Return (value, status, cooldown).

        Completion timestamps are conservative for start-window accounting; the
        lock serializes all dispatches. No credentials/URLs/bodies in receipts.
        """
        if method not in ('GET','HEAD'):raise GuardError('Read-only request required')
        with self._locked():
            s=self._read();now=self.clock();self._recover(s,now)
            s['events']=[t for t in s['events'] if now-t<WINDOW]
            until=max(s['blocked_until'],s['events'][0]+WINDOW if len(s['events'])>=LIMIT else 0)
            if now<until:raise WaitRequired((until-now)/1e9)
            s.update(last_ns=now,pending=True);self._write(s)
            status=None;cooldown=0
            try:
                value,status,cooldown=operation()
                if type(status) is not int or not 100<=status<=599 or not isinstance(cooldown,(int,float)) or not math.isfinite(cooldown) or cooldown<0:
                    raise GuardError('Invalid transport receipt')
                return value
            finally:
                end=self.clock()
                if end<now:raise GuardError('Clock changed during dispatch; pending reservation retained')
                s['events']=[t for t in s['events'] if end-t<WINDOW]+[end]
                # A failed attempt is charged, even if no response was received.
                hold=math.ceil(cooldown*1e9) if isinstance(cooldown,(int,float)) and math.isfinite(cooldown) and cooldown>=0 else WINDOW
                s.update(last_ns=end,pending=False,blocked_until=max(s['blocked_until'],end+hold))
                entry={'monotonic_ns':end,'method':method,'status':status if type(status) is int else None,'cooldown_ns':hold}
                s['receipts']=(s['receipts']+[entry])[-200:];self._write(s)
