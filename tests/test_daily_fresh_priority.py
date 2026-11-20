import fcntl

import pytest

from src.modules.daily_tender_run import fresh_priority as p


def test_fresh_priority_is_opt_in(monkeypatch):
    monkeypatch.delenv(p.ENV, raising=False)
    with p.fresh_preparation_priority():
        pass


def test_fresh_priority_lease_excludes_history_but_not_db_fence(tmp_path, monkeypatch):
    for name in ("mutation.lock", "fresh-procurement-priority.lock"):
        (tmp_path / name).touch(mode=0o600)
    monkeypatch.setenv(p.ENV, str(tmp_path.resolve()))
    with p.fresh_preparation_priority():
        with (tmp_path / "fresh-procurement-priority.lock").open() as fd, pytest.raises(BlockingIOError):
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with (tmp_path / "mutation.lock").open() as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with (tmp_path / "fresh-procurement-priority.lock").open() as fd:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)


def test_missing_or_symlink_lock_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(p.ENV, str(tmp_path.resolve()))
    with pytest.raises(FileNotFoundError), p.fresh_preparation_priority():
        pytest.fail("missing lock")
    (tmp_path / "target").touch()
    (tmp_path / "fresh-procurement-priority.lock").symlink_to(tmp_path / "target")
    with pytest.raises(OSError), p.fresh_preparation_priority():
        pytest.fail("symlink")
