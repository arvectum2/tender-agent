"""Disposable migrated PostgreSQL and R9 recovery of synthetic PRICE-01 records."""
from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

from scripts.acceptance.run_price01_staging import FLAGS, seed

ROOT = Path(__file__).resolve().parents[2]


def checked(response, status=200):
    if response.status_code != status:
        raise RuntimeError(f'{response.request.method} {response.request.url.path}: HTTP {response.status_code}, expected {status}')
    return response.json()


@contextmanager
def server(root, env):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    with (root / 'server.log').open('a') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'src.main:app', '--host',
            '127.0.0.1', '--port', str(port), '--no-access-log'], cwd=root, env=env, stdout=log, stderr=log)
        try:
            for _ in range(80):
                if proc.poll() is not None:
                    raise RuntimeError('Disposable HTTP server exited')
                try:
                    if httpx.get(origin + '/health', trust_env=False, timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('Disposable HTTP server not ready')
            yield origin
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def histories(origin, fixture, *, upload=False):
    base = '/api/saas/company-portfolio'
    path = base + '/cases/' + fixture['case_id']
    prices = path + '/price-scenarios'
    actual = prices + '/' + fixture['plan_id'] + '/actual-costs'
    norms = base + '/cost-norms/' + fixture['norm_key']
    owner = {'Authorization': 'Bearer ' + fixture['token']}
    foreign = {'Authorization': 'Bearer ' + fixture['foreign_token']}
    with httpx.Client(base_url=origin, trust_env=False, timeout=20) as c:
        actual_rows = checked(c.get(actual, headers=owner))
        snapshot = actual_rows['items'][0]['snapshot_id']
        evidence = {prices + '/' + fixture['plan_id'] + '/lines/1/evidence': 'QUOTE',
                    actual + '/' + snapshot + '/rows/PLANNED/1/evidence': 'TIMESHEET'}
        paths = [prices, actual, norms, path + '/historical-comparables', path + '/reviewed-contracts', *evidence]
        for url, kind in evidence.items():
            raw = b'%PDF-1.4\n% Synthetic ' + kind.encode() + b'\n1 0 obj<<>>endobj\n%%EOF'
            if upload:
                line = checked(c.get(url, headers=owner))
                checked(c.post(url, params={'line_sha256': line['line_sha256'], 'document_kind': kind,
                    'format_hint': 'pdf', 'confirm_user_supplied': True}, headers=owner, content=raw), 201)
            download = c.get(url + '/download', headers=owner)
            assert download.status_code == 200 and download.content == raw
            assert c.get(url + '/download', headers=foreign).status_code == 404
        result = {url: checked(c.get(url, headers=owner)) for url in paths}
        assert len(result[prices]['items']) == len(actual_rows['items']) == 1
        assert result[path + '/reviewed-contracts']['active_groups'] == []
        for url in paths:
            assert c.get(url, headers=foreign).status_code == 404, url
        assert checked(c.get(base + '/cost-norms', headers=foreign))['items'] == []
        return result


def main():
    if not __debug__:
        raise RuntimeError("Acceptance requires assertions enabled")
    # Reject inherited runtime settings including PG*, proxies and application credentials.
    keep = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL') if k in os.environ}
    os.environ.clear()
    os.environ.update(keep)
    os.environ["LC_ALL"] = "C"
    bindir = Path(subprocess.check_output(['pg_config', '--bindir'], text=True).strip())
    os.environ['PATH'] = str(bindir) + ':' + keep['PATH']
    from sqlalchemy import create_engine, text

    from scripts.ops.r9_recovery import (
        RecoveryError,
        create_backup,
        restore_backup,
        verify_backup,
    )

    with tempfile.TemporaryDirectory(prefix='ta-apr05-restore-', dir='/tmp') as directory:
        root = Path(directory).resolve()
        data, sock = root / 'pg', root / 'sock'
        sock.mkdir(mode=0o700)
        appdata, restored = root / 'appdata', root / 'restored'
        appdata.mkdir(mode=0o700)
        (appdata / 'synthetic-recovery-marker.txt').write_bytes(b'APR05 synthetic recovery fixture\n')
        os.chdir(root)
        url = 'postgresql+psycopg://apr05_acceptance@localhost/postgres?host=' + str(sock) + '&port=5432'
        target = url.replace('/postgres?', '/apr05_restored?')
        password = secrets.token_urlsafe(36)
        env = {**os.environ, 'PYTHONPATH': str(ROOT), 'AI_CORP_DATABASE_URL': url,
               'AI_CORP_ARVECTUM_DATA_DIR': str(appdata), 'AI_CORP_SAAS_FOUNDATION_ENABLED': 'true',
               'AI_CORP_PILOT_AUTH_ENABLED': 'true', 'AI_CORP_PILOT_AUTH_USERNAME': 'price01-operator',
               'AI_CORP_PILOT_AUTH_PASSWORD': password, 'AI_CORP_ARVECTUM_REDIS_ENABLED': 'false',
               'TENDER_LEARNING_CAPTURE_ENABLED': '0', 'AI_CORP_ALLOWED_HOSTS': '127.0.0.1'}
        env.update({'AI_CORP_SAAS_COMPANY_' + f.upper() + '_ENABLED': 'true' for f in FLAGS})

        def run(*args, **kwargs):
            subprocess.run(args, cwd=root, env=env, check=True, timeout=120, **kwargs)

        def connect_guard(address, migrated=False):
            engine = create_engine(address, isolation_level='AUTOCOMMIT')
            try:
                with engine.connect() as conn:
                    assert Path(conn.execute(text('SHOW data_directory')).scalar_one()).resolve() == data
                    if migrated:
                        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '123_application_review'
            finally:
                engine.dispose()

        try:
            run(str(bindir / 'initdb'), '-D', str(data), '-U', 'apr05_acceptance', '-A', 'trust', '--no-locale', '-E', 'UTF8', stdout=subprocess.DEVNULL)
            run(str(bindir / 'pg_ctl'), '-D', str(data), '-l', str(root / 'postgres.log'), '-o', f"-h '' -k {sock}", '-w', 'start')
            connect_guard(url)
            run(sys.executable, '-c', 'from alembic.config import Config; from alembic import command; '
                f'c=Config({str(ROOT / "alembic.ini")!r}); c.set_main_option("script_location",{str(ROOT / "migrations")!r}); command.upgrade(c,"head")', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            connect_guard(url, migrated=True)
            with server(root, env) as origin:
                fixture = seed(origin, True, password)
                before = histories(origin, fixture, upload=True)
            print('MIGRATED_API_SEED_PASS', flush=True)
            backup = create_backup(database_url=url, data_dir=appdata, output_dir=root / 'backups', quiesced=True)
            manifest = verify_backup(backup)
            assert len(manifest['tenant_scope']) == 2
            tampered = root / 'tampered'
            shutil.copytree(backup, tampered)
            with (tampered / 'database.dump').open('ab') as handle:
                handle.write(b'synthetic alteration')
            try:
                verify_backup(tampered)
            except RecoveryError as exc:
                assert 'checksum mismatch' in str(exc)
            else:
                raise AssertionError('Corrupt backup accepted')
            run(str(bindir / 'createdb'), '-h', str(sock), '-p', '5432', '-U', 'apr05_acceptance', 'apr05_restored')
            connect_guard(target)
            options = {'database_url': target, 'data_dir': restored, 'backup_dir': backup, 'quiesced': True}
            try:
                restore_backup(**options, expected_tenants={'wrong-scope'})
            except RecoveryError:
                pass
            else:
                raise AssertionError('Wrong scope restore accepted')
            receipt = restore_backup(**options, expected_tenants=set(manifest['tenant_scope']))
            assert receipt['database_restored'] and receipt['filesystem_restored']
            assert (restored / 'synthetic-recovery-marker.txt').read_bytes() == (appdata / 'synthetic-recovery-marker.txt').read_bytes()
            connect_guard(target, migrated=True)
            target_env = {**env, 'AI_CORP_DATABASE_URL': target, 'AI_CORP_ARVECTUM_DATA_DIR': str(restored)}
            with (
                server(root, {**target_env, 'AI_CORP_SAAS_COMPANY_PRICE_SCENARIOS_ENABLED': 'false'}) as origin,
                httpx.Client(base_url=origin, trust_env=False, timeout=20) as client,
            ):
                for path in before:
                    assert client.get(path, headers={'Authorization': 'Bearer ' + fixture['token']}).status_code == 404, path
            with server(root, target_env) as origin:
                assert histories(origin, fixture) == before
            print('APR05_R9_RESTORE_PASS: actual migration 122, 7 exact API histories, 2 evidence downloads, tenant denial, wrong-scope and corrupt-backup rejection, restart kill switch', flush=True)
            print('DISPOSABLE_BACKUP_SHA256', hashlib.sha256((backup / 'database.dump').read_bytes()).hexdigest(), flush=True)
        except Exception:
            if (root / 'postgres.log').exists():
                print((root / 'postgres.log').read_text()[-2500:], file=sys.stderr)
            raise
        finally:
            if (data / 'postmaster.pid').exists():
                run(str(bindir / 'pg_ctl'), '-D', str(data), '-m', 'fast', '-w', 'stop')
            os.chdir(ROOT)


if __name__ == '__main__':
    main()
