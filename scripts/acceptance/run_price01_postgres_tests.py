"""Isolated PRICE-01 acceptance on a disposable local Unix-socket PostgreSQL."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    bindir=Path(subprocess.check_output(['pg_config','--bindir'],text=True).strip())
    with tempfile.TemporaryDirectory(prefix='ta-price01-pg-',dir='/tmp') as directory:
        root=Path(directory).resolve()
        data=root/'pg';sock=root/'socket';sock.mkdir(mode=0o700)
        (root/'appdata').mkdir(mode=0o700)
        env=os.environ.copy()
        env.pop('AI_CORP_ORIGINAL_DATABASE_URL',None)
        env.update(AI_CORP_DATABASE_URL=f"postgresql+psycopg://price01_acceptance@/postgres?host={sock}&port=5432",
                   AI_CORP_ARVECTUM_DATA_DIR=str(root/'appdata'),RUN_R8_POSTGRES_INTEGRATION='1',
                   PRICE01_ISOLATED_PG_DATA=str(data),TENDER_LEARNING_CAPTURE_ENABLED='0')
        def run(*args,timeout=90):
            subprocess.run(args,cwd=ROOT,env=env,check=True,timeout=timeout)
        started=False
        try:
            run(str(bindir/'initdb'),'-D',str(data),'-U','price01_acceptance','-A','trust','--no-locale','-E','UTF8')
            run(str(bindir/'pg_ctl'),'-D',str(data),'-l',str(root/'postgres.log'),'-o',f"-h '' -k {sock}",'-w','start')
            started=True
            run(sys.executable,'-m','alembic','upgrade','head',timeout=120)
            run(sys.executable,'-m','pytest','-q','tests/test_apr05_saas_foundation.py','-k','price01_postgres_concurrent_norm_and_estimate','--run-postgres','--run-integration','--tb=short',timeout=120)
        finally:
            if started or (data/'postmaster.pid').exists():
                subprocess.run([str(bindir/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'],env=env,check=True,timeout=30)


if __name__=='__main__':
    main()
