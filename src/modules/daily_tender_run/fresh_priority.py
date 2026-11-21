"""Optional host-local priority lease across the shared DP processing boundary.

No global mutation fence remains held during preparation: the exclusive
priority lease prevents cooperating historical writers from starting.
"""
from __future__ import annotations

import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ENV = "ARVECTUM_DAILY_FRESH_PRIORITY_DIRECTORY"


@contextmanager
def _lock(path: Path, timeout: float) -> Iterator[None]:
    import fcntl

    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o022:
            raise RuntimeError("unsafe historical priority lock")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("fresh procurement priority lease timed out")
                time.sleep(0.25)
        yield
    finally:
        os.close(fd)


@contextmanager
def fresh_preparation_priority() -> Iterator[None]:
    value = os.environ.get(ENV)
    if not value:
        yield
        return
    root = Path(value)
    if not root.is_absolute() or root.resolve() != root or not root.is_dir():
        raise RuntimeError("invalid fresh procurement priority directory")
    st = root.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise RuntimeError("unsafe fresh procurement priority directory")
    with _lock(root / "fresh-procurement-priority.lock", 2400):
        # Let existing source transactions reconcile before starting fresh work.
        with _lock(root / "mutation.lock", 2400):
            pass
        yield
