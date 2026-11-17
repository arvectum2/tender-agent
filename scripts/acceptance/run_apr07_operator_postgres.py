"""Disposable Unix-socket PostgreSQL acceptance for the APR07 operator read-only CLI."""
from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from scripts.ops.apr07_analysis_window import snapshot
from src.tender_research.models import TenderAnalysisJob


def main():
    bindir = Path(subprocess.check_output(['pg_config', '--bindir'], text=True).strip())
    now = datetime(2026, 11, 17, 8, tzinfo=UTC)
    with tempfile.TemporaryDirectory(prefix='ta-apr07-pg-', dir='/tmp') as folder:
        root = Path(folder).resolve()
        data, sock = root / 'pg', root / 'socket'
        sock.mkdir(mode=0o700)
        env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
        env.update(LC_ALL='C', LANG='C')
        def run(*args, timeout=60):
            subprocess.run(args, env=env, check=True, timeout=timeout, capture_output=True)
        def url(role):
            return f'postgresql+psycopg://{role}@/postgres?host={sock}&port=55437'
        started = False
        try:
            run(str(bindir / 'initdb'), '-D', str(data), '-U', 'apr07_fixture_owner', '-A', 'trust', '--no-locale', '-E', 'UTF8')
            run(str(bindir / 'pg_ctl'), '-D', str(data), '-l', str(root/'pg.log'), '-o', f"-h '' -k {sock} -p 55437", '-w', 'start')
            started = True
            engine = create_engine(url('apr07_fixture_owner'))
            try:
                TenderAnalysisJob.__table__.create(engine)
                with engine.begin() as conn:
                    conn.exec_driver_sql('CREATE ROLE apr07_observer LOGIN')
                    conn.exec_driver_sql('CREATE ROLE apr07_writer LOGIN')
                    conn.exec_driver_sql('CREATE ROLE apr07_broad_reader LOGIN')
                    conn.exec_driver_sql('CREATE ROLE apr07_partial_reader LOGIN')
                    conn.exec_driver_sql('CREATE ROLE apr07_extra_column NOLOGIN')
                    conn.exec_driver_sql('CREATE ROLE apr07_inherited_reader LOGIN INHERIT')
                    conn.exec_driver_sql('GRANT apr07_extra_column TO apr07_inherited_reader')
                    conn.exec_driver_sql('GRANT USAGE ON SCHEMA public TO apr07_broad_reader, apr07_partial_reader, apr07_inherited_reader')
                    conn.exec_driver_sql('GRANT SELECT ON public.tender_analysis_jobs TO apr07_broad_reader')
                    conn.exec_driver_sql('GRANT SELECT (status) ON public.tender_analysis_jobs TO apr07_partial_reader')
                    conn.exec_driver_sql('GRANT SELECT (registry_number) ON public.tender_analysis_jobs TO apr07_extra_column')
                    conn.exec_driver_sql('GRANT SELECT (job_type,status,created_at,started_at,finished_at,updated_at) ON public.tender_analysis_jobs TO apr07_inherited_reader')
                    conn.exec_driver_sql('GRANT USAGE ON SCHEMA public TO apr07_observer, apr07_writer')
                    conn.exec_driver_sql('GRANT SELECT (job_type,status,created_at,started_at,finished_at,updated_at) ON public.tender_analysis_jobs TO apr07_observer, apr07_writer')
                    conn.exec_driver_sql('GRANT UPDATE (status) ON public.tender_analysis_jobs TO apr07_writer')
                    conn.execute(text("""
                        INSERT INTO tender_analysis_jobs (id, job_type, registry_number, status, progress_percent, created_at, started_at, finished_at, updated_at)
                        SELECT 'fixture-' || i, 'analyze', 'private-fixture', 'completed', 100,
                          :now - interval '1 minute' - i * interval '1 second',
                          :now - interval '1 minute', :now - interval '1 minute', :now - interval '1 minute'
                        FROM generate_series(1,100) AS i
                    """), {'now': now})
                result = snapshot(url('apr07_observer'), now=now)
                assert result['terminal_jobs'] == 100 and result['state'] == 'OBSERVED_NOT_APPROVED'
                assert result['queue_to_finished_seconds']['p95'] == 95
                assert result['clean_completion_rate'] == 1.0 and not result['rolling_production_slo_approved']
                assert 'private-fixture' not in str(result)
                for role in ('apr07_fixture_owner', 'apr07_writer', 'apr07_broad_reader', 'apr07_partial_reader', 'apr07_inherited_reader'):
                    try:
                        snapshot(url(role), now=now)
                    except PermissionError:
                        pass
                    else:
                        raise AssertionError('Privileged role was accepted')
                with engine.begin() as conn:
                    conn.exec_driver_sql('ALTER TABLE public.tender_analysis_jobs ENABLE ROW LEVEL SECURITY')
                try:
                    snapshot(url('apr07_observer'), now=now)
                except PermissionError:
                    pass
                else:
                    raise AssertionError('RLS-filtered table was accepted as global evidence')
                with engine.begin() as conn:
                    conn.exec_driver_sql('ALTER TABLE public.tender_analysis_jobs DISABLE ROW LEVEL SECURITY')
                assert snapshot(url('apr07_observer'), now=now) == result
                observer = create_engine(url('apr07_observer'))
                try:
                    for statement in ('SELECT registry_number FROM tender_analysis_jobs', 'UPDATE tender_analysis_jobs SET status=\'failed\''):
                        try:
                            with observer.begin() as conn:
                                conn.exec_driver_sql(statement)
                        except SQLAlchemyError:
                            pass
                        else:
                            raise AssertionError('Restricted observer acquired disallowed privilege')
                finally:
                    observer.dispose()
                with engine.connect() as conn:
                    assert conn.execute(text("SELECT count(*) FROM tender_analysis_jobs WHERE status='completed'")).scalar_one() == 100
            finally:
                engine.dispose()
        except subprocess.CalledProcessError:
            log = root / 'pg.log'
            if log.is_file():
                print(log.read_text(errors='replace')[-2500:])
            raise
        finally:
            if started or (data/'postmaster.pid').exists():
                run(str(bindir/'pg_ctl'), '-D', str(data), '-m', 'fast', '-w', 'stop')
    print('APR07_POSTGRES_OPERATOR_READONLY_PASS: 100 terminal rows, p95=95s, owner/writer/broad/partial/inherited reader denied, RLS denied, sensitive field/write denied, cluster removed')


if __name__ == '__main__':
    main()
