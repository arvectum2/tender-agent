"""Supervised one-card runner candidate. Local acceptance only; no live activation.

The supervisor owns the wall deadline. A timed-out broker cannot continue to
start upstream requests; killing it retains the durable pending reservation.
One canonical private directory per designated host, no implicit initialisation.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from scripts.research.b2b_network_guard import EgressGate, GuardError

ROOT_PARTS=('Library','Application Support','Arvectum','B2B-private')
MAX_RUN_SECONDS=65


def canonical_root():
    return Path.home().joinpath(*ROOT_PARTS)


def private_dir(path):
    p=Path(path);s=p.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o077 or p.resolve()!=p.absolute():raise GuardError('Canonical private directory required')
    return p


@contextmanager
def single_runner(root):
    root=private_dir(root)
    fd=os.open(root/'runner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        EgressGate._private(fd)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise GuardError('Another B2B runner is active') from None
        yield
    finally:os.close(fd)


def supervise(command,payload,*,seconds=MAX_RUN_SECONDS,env=None):
    if not 0<seconds<=MAX_RUN_SECONDS:raise GuardError('Invalid supervisor deadline')
    # A separate process session includes broker, renderer and inherited children.
    # On deadline, stop the upstream broker even if a response is trickling in.
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True,env=env)
    try:
        try:out,_err=process.communicate(json.dumps(payload),timeout=seconds)
        except subprocess.TimeoutExpired:raise GuardError('Runner deadline exceeded; no automatic retry') from None
        if process.returncode or len(out)>65536:raise GuardError('Runner failed or invalid receipt')
        try:receipt=json.loads(out)
        except ValueError:raise GuardError('Invalid runner receipt') from None
        if not isinstance(receipt,dict):raise GuardError('Invalid runner receipt')
        return receipt
    finally:
        # PID is the process-group leader; no other process group is targeted.
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        if process.poll() is None:process.wait(timeout=5)
        if process.stdin:process.stdin.close()
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()


def sandbox_renderer(adapter,*,origin,card,directory,mode):
    if sys.platform!='darwin':raise GuardError('macOS network isolation required')
    left=adapter.deadline-time.monotonic()
    if left<=0:raise GuardError('Runner deadline expired')
    with adapter.serve() as port:
        profile=f'(version 1)(allow default)(deny network*)(allow network-bind (local unix-socket))(allow network-outbound (remote tcp "localhost:{port}"))'
        cfg={'port':port,'token':adapter.token,'origin':origin,'card':card,'directory':str(directory),'mode':mode}
        result=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,sys.executable,'-m','scripts.research.b2b_renderer_worker'],input=json.dumps(cfg),text=True,capture_output=True,timeout=max(1,min(45,left)),check=False)
        if result.returncode or len(result.stdout)>65536:raise GuardError('Isolated renderer failed')
        try:value=json.loads(result.stdout)
        except ValueError:raise GuardError('Invalid renderer receipt') from None
        if not isinstance(value,dict) or value.get('sandbox_negative_probe') is not True:raise GuardError('Renderer confinement not demonstrated')
        return value


def main():
    import argparse

    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--check-local',action='store_true');group.add_argument('--offline-acceptance',action='store_true');args=parser.parse_args()
    if args.offline_acceptance:
        print(json.dumps(supervise([sys.executable,'-m','scripts.research.b2b_isolated_adapter_fixture'],{},seconds=MAX_RUN_SECONDS)));return 0
    root=canonical_root()
    print(json.dumps({'state':'LOCAL_RUNNER_CANDIDATE','macos':sys.platform=='darwin','private_root_exists':root.is_dir(),'sandbox_executable':Path('/usr/bin/sandbox-exec').is_file(),'live_enabled':False,'deadline_seconds':MAX_RUN_SECONDS}))
    return 0


if __name__=='__main__':raise SystemExit(main())
