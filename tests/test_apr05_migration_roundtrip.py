"""APR-05 reversible schema migration without touching a live runtime DB."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from src.shared.config.settings import invalidate_settings_cache

TABLES = {
    "saas_tenants", "saas_members", "saas_invitations", "saas_access_tokens",
    "saas_legal_acceptances", "saas_usage_counters", "saas_runs",
    "saas_payment_evidence", "saas_audit_events",
}


def test_apr05_migration_forward_rollback_and_reupgrade(tmp_path: Path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "reversible_apr05.sqlite"
    db_url = "sqlite:///" + str(db_file)
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    invalidate_settings_cache()
    cfg = Config(str(repo / "alembic.ini"))
    # A minimal existing company table models the APR-04 predecessor FK.
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE customer_profiles (id VARCHAR PRIMARY KEY, customer_id VARCHAR(64) UNIQUE NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO customer_profiles (id, customer_id) VALUES ('existing-id','CUS-preexisting')"
        ))
    engine.dispose()
    try:
        command.stamp(cfg, "105_add_company_profile_store")
        command.upgrade(cfg, "106_add_saas_foundation")
        engine = create_engine(db_url)
        assert TABLES <= set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "106_add_saas_foundation"
            assert conn.execute(text("SELECT count(*) FROM customer_profiles")).scalar() == 1
        engine.dispose()
        command.downgrade(cfg, "105_add_company_profile_store")
        engine = create_engine(db_url)
        assert not TABLES.intersection(inspect(engine).get_table_names())
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM customer_profiles")).scalar() == 1
        engine.dispose()
        command.upgrade(cfg, "106_add_saas_foundation")
        engine = create_engine(db_url)
        assert TABLES <= set(inspect(engine).get_table_names())
        engine.dispose()
    finally:
        invalidate_settings_cache()
