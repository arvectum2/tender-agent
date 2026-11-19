"""Priority entrants are not starved by repeated historical batches."""
import fcntl
import threading
from scripts.research import autonomous_runner as m


def runner(tmp_path):
    r=m.Runner.__new__(m.Runner)
    r.run=tmp_path
    r.write_mutex=threading.Lock()
    return r


def test_waiting_priority_writer_gets_mutation_lock(tmp_path,monkeypatch):
    r=runner(tmp_path)
    waiting=(tmp_path/'fresh-procurement-priority.lock').open('a')
    fcntl.flock(waiting,fcntl.LOCK_EX)
    yielded=[]
    def sleep(seconds):
        # Runner must release mutation BEFORE waiting for priority.
        with (tmp_path/'mutation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yielded.append(seconds)
        waiting.close()
    monkeypatch.setattr(m.time,'sleep',sleep)
    with r.mutation_guard():
        assert yielded==[2]
    assert waiting.closed


def test_importer_can_claim_priority_during_archive_batch(tmp_path):
    r=runner(tmp_path)
    with r.mutation_guard():
        with (tmp_path/'fresh-procurement-priority.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # No stale marker following exit.
    with r.mutation_guard():
        pass
