"""Local operator-only rolling analysis snapshot, never uses application DB defaults."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.modules.ops_observability.analysis_window import measure_analysis_window

DSN_ENV = 'AI_CORP_APR07_READONLY_DATABASE_URL'


def operator_url(value: str):
    """Permit only an explicitly selected local socket and dedicated login."""
    url = make_url(value)
    host = url.query.get('host')
    port = url.query.get('port', '5432')
    if (url.drivername != 'postgresql+psycopg' or url.host is not None or url.port is not None
            or not url.username or not url.database or not isinstance(host, str)
            or ',' in host or not Path(host).is_absolute() or not Path(host).is_dir()
            or not isinstance(port, str) or not port.isascii() or not port.isdecimal()
            or not 1 <= int(port) <= 65535
            or any(os.environ.get(k) for k in ('PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS'))
            or set(url.query) - {'host', 'port'}):
        raise ValueError('Explicit local PostgreSQL Unix socket and dedicated role required')
    return url.update_query_dict({'port': port})


def snapshot(value: str, *, now: datetime, days: int = 7) -> dict:
    engine = create_engine(operator_url(value), isolation_level='REPEATABLE READ', pool_pre_ping=True,
                           connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as conn, conn.begin():
            conn.exec_driver_sql('SET TRANSACTION READ ONLY')
            conn.exec_driver_sql('SET LOCAL search_path TO pg_catalog, public')
            conn.exec_driver_sql("SET LOCAL statement_timeout = '15000ms'")
            allowed = conn.execute(text("""
                SELECT NOT (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR r.rolbypassrls)
                    AND NOT has_table_privilege(current_user, 'public.tender_analysis_jobs', 'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
                    AND NOT has_any_column_privilege(current_user, 'public.tender_analysis_jobs', 'INSERT,UPDATE,REFERENCES')
                    AND NOT pg_has_role(current_user, c.relowner, 'MEMBER')
                FROM pg_roles r CROSS JOIN pg_class c
                WHERE r.rolname = current_user AND c.oid = 'public.tender_analysis_jobs'::regclass
            """)).scalar_one()
            if allowed is not True:
                raise PermissionError('Dedicated non-writing operator role required')
            with Session(bind=conn, autoflush=False) as session:
                return measure_analysis_window(session, now=now, days=days)
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, choices=range(1, 31), default=7)
    args = parser.parse_args(argv)
    value = os.environ.get(DSN_ENV)
    if not value:
        print(f'APR07_OPERATOR_BLOCKED: explicit {DSN_ENV} required', file=sys.stderr)
        return 2
    try:
        result = snapshot(value, now=datetime.now(UTC), days=args.days)
    except (SQLAlchemyError, OSError, ValueError):
        # Never emit DB URL, query arguments, role name or connection details.
        print('APR07_OPERATOR_BLOCKED: local read-only database or measurement unavailable', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
