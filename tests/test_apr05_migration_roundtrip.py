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




def test_standalone_cli_db_registry_covers_legacy_and_saas_fk_targets():
    """Regression: an import auto-fix must not strip ORM table registration."""
    import subprocess
    import sys

    script = """
from src.shared.db import models as registry
from src.shared.db.base import Base
from sqlalchemy import create_engine
need = {'customer_profiles', 'pilot_projects', 'procurement_cases',
        'tender_analysis_runs', 'saas_tenants', 'saas_members', 'saas_runs'}
assert need <= set(Base.metadata.tables), need - set(Base.metadata.tables)
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
engine.dispose()
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True, capture_output=True, text=True, timeout=20,
    )


def test_company_portfolio_migration_preserves_legacy_and_blocks_history_downgrade(tmp_path, monkeypatch):
    import pytest

    db_url = "sqlite:///" + str(tmp_path / "company_portfolio.sqlite")
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (("procurement_cases", "id"), ("saas_tenants", "tenant_id"), ("saas_members", "id")):
                conn.execute(text(f"CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)"))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('existing')"))
        command.stamp(cfg, "107_add_procurement_learning_observations")
        command.upgrade(cfg, "108_company_portfolio_decisions")
        assert "company_portfolio_decisions" in inspect(engine).get_table_names()
        command.downgrade(cfg, "107_add_procurement_learning_observations")
        assert "company_portfolio_decisions" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "108_company_portfolio_decisions")
        with engine.begin() as conn:
            assert conn.execute(text("SELECT count(*) FROM procurement_cases")).scalar_one() == 1
            conn.execute(text("INSERT INTO company_portfolio_decisions (id, case_id, tenant_id, member_id, revision, action, rationale, idempotency_key, created_at) VALUES ('d1','existing','existing','existing',1,'GO','test','test-key','2026-11-15 00:00:00')"))
        with pytest.raises(RuntimeError, match="Cannot remove populated"):
            command.downgrade(cfg, "107_add_procurement_learning_observations")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM company_portfolio_decisions")).scalar_one() == 1
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_company_evidence_migration_preserves_profile_and_blocks_populated_downgrade(tmp_path, monkeypatch):
    import pytest

    db_url = "sqlite:///" + str(tmp_path / "company_evidence.sqlite")
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (("procurement_cases", "id"), ("saas_tenants", "tenant_id"), ("saas_members", "id"), ("saas_runs", "run_id"), ("company_profile_fact_versions", "id")):
                conn.execute(text(f"CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)"))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('existing')"))
        command.stamp(cfg, "108_company_portfolio_decisions")
        command.upgrade(cfg, "109_company_portfolio_evidence")
        assert "company_portfolio_evidence" in inspect(engine).get_table_names()
        command.downgrade(cfg, "108_company_portfolio_decisions")
        assert "company_portfolio_evidence" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "109_company_portfolio_evidence")
        with engine.begin() as conn:
            assert conn.execute(text("SELECT count(*) FROM company_profile_fact_versions")).scalar_one() == 1
            conn.execute(text("INSERT INTO company_portfolio_evidence (id, case_id, tenant_id, member_id, run_id, profile_fact_id, source_snapshot_sha256, created_at) VALUES ('e1','existing','existing','existing','existing','existing',:sha,'2026-11-15 00:00:00')"), {"sha": "a" * 64})
        with pytest.raises(RuntimeError, match="Cannot remove populated"):
            command.downgrade(cfg, "108_company_portfolio_decisions")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM company_portfolio_evidence")).scalar_one() == 1
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_company_discovery_migration_preserves_predecessor_and_receipts(tmp_path, monkeypatch):
    import pytest

    db_url = "sqlite:///" + str(tmp_path / "discovery.sqlite")
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (("saas_tenants", "tenant_id"), ("saas_members", "id"), ("company_profile_fact_versions", "id")):
                conn.execute(text(f"CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)"))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('existing')"))
        command.stamp(cfg, "109_company_portfolio_evidence")
        command.upgrade(cfg, "110_company_discovery_runs")
        assert "company_discovery_runs" in inspect(engine).get_table_names()
        command.downgrade(cfg, "109_company_portfolio_evidence")
        assert "company_discovery_runs" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "110_company_discovery_runs")
        with engine.begin() as conn:
            assert conn.execute(text("SELECT count(*) FROM company_profile_fact_versions")).scalar_one() == 1
            conn.execute(text("INSERT INTO company_discovery_runs (id, tenant_id, member_id, profile_fact_id, run_day, status, plan_json, results_json, created_at, updated_at) VALUES ('r1','existing','existing','existing','2026-11-16','PENDING','{}','[]','2026-11-16','2026-11-16')"))
        with pytest.raises(RuntimeError, match="Cannot remove populated"):
            command.downgrade(cfg, "109_company_portfolio_evidence")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM company_discovery_runs")).scalar_one() == 1
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_company_schedule_migration_preserves_existing_runs_and_blocks_data_loss(tmp_path, monkeypatch):
    import pytest

    db_url = "sqlite:///" + str(tmp_path / "schedule.sqlite")
    monkeypatch.setenv("AI_CORP_DATABASE_URL", db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (("saas_tenants", "tenant_id"), ("saas_members", "id"), ("company_profile_fact_versions", "id")):
                conn.execute(text(f"CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)"))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('existing')"))
        command.stamp(cfg, "109_company_portfolio_evidence")
        command.upgrade(cfg, "110_company_discovery_runs")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO company_discovery_runs (id, tenant_id, member_id, profile_fact_id, run_day, status, plan_json, results_json, created_at, updated_at) VALUES ('r1','existing','existing','existing','2026-11-16','PENDING','{}','[]','2026-11-16','2026-11-16')"))
        command.upgrade(cfg, "111_company_discovery_schedule")
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT attempts_json FROM company_discovery_runs")) == "[]"
            assert conn.scalar(text("SELECT count(*) FROM company_discovery_schedules")) == 0
        command.downgrade(cfg, "110_company_discovery_runs")
        assert "company_discovery_schedules" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "111_company_discovery_schedule")
        with engine.begin() as conn:
            assert conn.scalar(text("SELECT count(*) FROM company_discovery_runs")) == 1
            conn.execute(text("UPDATE company_discovery_runs SET attempts_json = :attempt"), {"attempt": '[{"step":0}]'})
        with pytest.raises(RuntimeError, match="Cannot discard"):
            command.downgrade(cfg, "110_company_discovery_runs")
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT attempts_json FROM company_discovery_runs")) == '[{"step":0}]'
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_commercial_capture_migration_preserves_immutable_history(tmp_path, monkeypatch):
    import pytest

    db_url = 'sqlite:///' + str(tmp_path/'commercial.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL', db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (('saas_tenants','tenant_id'),('saas_members','id'),('procurement_cases','id')):
                conn.execute(text(f'CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('fixture')"))
        command.stamp(cfg,'111_company_discovery_schedule')
        command.upgrade(cfg,'112_commercial_card_snapshots')
        assert 'commercial_card_snapshots' in inspect(engine).get_table_names()
        command.downgrade(cfg,'111_company_discovery_schedule')
        assert 'commercial_capture_attempts' not in inspect(engine).get_table_names()
        command.upgrade(cfg,'112_commercial_card_snapshots')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO commercial_capture_attempts (id, tenant_id, case_id, member_id, capture_day, source_url, created_at) VALUES ('a','fixture','fixture','fixture','2026-11-16','https://workspace.ru/tenders/fixture-19043/','2026-11-16')"))
        with pytest.raises(RuntimeError, match='Cannot discard'):
            command.downgrade(cfg,'111_company_discovery_schedule')
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT count(*) FROM commercial_capture_attempts'))==1
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_commercial_attachment_migration_preserves_originals(tmp_path, monkeypatch):
    import pytest

    db_url = 'sqlite:///' + str(tmp_path/'attachment.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL', db_url)
    invalidate_settings_cache()
    cfg = Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table, identity in (('saas_tenants','tenant_id'),('saas_members','id'),('procurement_cases','id')):
                conn.execute(text(f'CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('fixture')"))
        command.stamp(cfg,'111_company_discovery_schedule')
        command.upgrade(cfg,'113_commercial_attachment_evidence')
        assert 'commercial_attachment_evidence' in inspect(engine).get_table_names()
        command.downgrade(cfg,'112_commercial_card_snapshots')
        assert 'commercial_attachment_evidence' not in inspect(engine).get_table_names()
        command.upgrade(cfg,'113_commercial_attachment_evidence')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO commercial_capture_attempts (id,tenant_id,case_id,member_id,capture_day,source_url,created_at) VALUES ('a','fixture','fixture','fixture','2026-11-16','https://workspace.ru/tenders/fixture-19043/','2026-11-16')"))
            conn.execute(text("INSERT INTO commercial_attachment_evidence (id,attempt_id,member_id,candidate_id,source_url,raw_bytes,inspection_json,created_at) VALUES ('e','a','fixture','fixture','https://workspace.ru/docs/spec.docx',:raw,'{}','2026-11-16')"),{'raw':b'fixture'})
        with pytest.raises(RuntimeError, match='Cannot discard'):
            command.downgrade(cfg,'112_commercial_card_snapshots')
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT raw_bytes FROM commercial_attachment_evidence'))==b'fixture'
    finally:
        engine.dispose()
        invalidate_settings_cache()


def test_requirement_review_migration_preserves_history(tmp_path, monkeypatch):
    import pytest

    db_url='sqlite:///'+str(tmp_path/'review.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL',db_url);invalidate_settings_cache()
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));engine=create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table in ('commercial_attachment_evidence','saas_members','company_profile_fact_versions','company_document_versions'):
                conn.execute(text(f'CREATE TABLE {table} (id VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} (id) VALUES ('fixture')"))
        command.stamp(cfg,'113_commercial_attachment_evidence');command.upgrade(cfg,'114_commercial_requirement_reviews')
        assert 'commercial_requirement_reviews' in inspect(engine).get_table_names()
        command.downgrade(cfg,'113_commercial_attachment_evidence');command.upgrade(cfg,'114_commercial_requirement_reviews')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO commercial_requirement_reviews (id,attachment_id,member_id,fragment_key,revision,idempotency_key,profile_fact_id,review_json,created_at) VALUES ('r','fixture','fixture','fragment',1,'replay','fixture','{}','2026-11-16')"))
        with pytest.raises(RuntimeError,match='Cannot discard'):
            command.downgrade(cfg,'113_commercial_attachment_evidence')
        with engine.connect() as conn:assert conn.scalar(text('SELECT count(*) FROM commercial_requirement_reviews'))==1
    finally:
        engine.dispose();invalidate_settings_cache()


def test_company_lifecycle_migration_preserves_history(tmp_path, monkeypatch):
    import pytest

    db_url='sqlite:///'+str(tmp_path/'lifecycle.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL',db_url);invalidate_settings_cache()
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));engine=create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table,identity in (('procurement_cases','id'),('saas_tenants','tenant_id'),('saas_members','id'),('company_portfolio_decisions','id')):
                conn.execute(text(f'CREATE TABLE {table} ({identity} VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} ({identity}) VALUES ('fixture')"))
        command.stamp(cfg,'114_commercial_requirement_reviews');command.upgrade(cfg,'115_company_case_lifecycle')
        assert 'company_case_lifecycle_events' in inspect(engine).get_table_names()
        command.downgrade(cfg,'114_commercial_requirement_reviews');command.upgrade(cfg,'115_company_case_lifecycle')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO company_case_lifecycle_events (id,case_id,tenant_id,member_id,go_decision_id,revision,stage,event_json,idempotency_key,created_at) VALUES ('e','fixture','fixture','fixture','fixture',1,'READY','{}','fixture-key','2026-11-16')"))
        with pytest.raises(RuntimeError,match='Cannot discard'):
            command.downgrade(cfg,'114_commercial_requirement_reviews')
        with engine.connect() as conn:assert conn.scalar(text('SELECT count(*) FROM company_case_lifecycle_events'))==1
    finally:
        engine.dispose();invalidate_settings_cache()


def test_readiness_evidence_migration_preserves_bindings(tmp_path, monkeypatch):
    import pytest

    db_url='sqlite:///'+str(tmp_path/'readiness.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL',db_url);invalidate_settings_cache()
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));engine=create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table in ('company_case_lifecycle_events','commercial_capture_attempts','saas_members'):
                conn.execute(text(f'CREATE TABLE {table} (id VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} (id) VALUES ('fixture')"))
        command.stamp(cfg,'115_company_case_lifecycle');command.upgrade(cfg,'116_company_readiness_evidence')
        assert 'company_readiness_evidence' in inspect(engine).get_table_names()
        command.downgrade(cfg,'115_company_case_lifecycle');command.upgrade(cfg,'116_company_readiness_evidence')
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO company_readiness_evidence (id,ready_event_id,attempt_id,member_id,projection_sha256,projection_json,created_at) VALUES ('e','fixture','fixture','fixture','digest','{}','2026-11-16')"))
        with pytest.raises(RuntimeError,match='Cannot discard'):
            command.downgrade(cfg,'115_company_case_lifecycle')
        with engine.connect() as conn:assert conn.scalar(text('SELECT count(*) FROM company_readiness_evidence'))==1
    finally:
        engine.dispose();invalidate_settings_cache()


def test_lifecycle_artifact_migration_preserves_bytes(tmp_path, monkeypatch):
    import pytest

    db_url='sqlite:///'+str(tmp_path/'artifact.sqlite')
    monkeypatch.setenv('AI_CORP_DATABASE_URL',db_url);invalidate_settings_cache()
    cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));engine=create_engine(db_url)
    try:
        with engine.begin() as conn:
            for table in ('company_case_lifecycle_events','saas_members'):
                conn.execute(text(f'CREATE TABLE {table} (id VARCHAR PRIMARY KEY)'))
                conn.execute(text(f"INSERT INTO {table} (id) VALUES ('fixture')"))
        command.stamp(cfg,'116_company_readiness_evidence');command.upgrade(cfg,'117_company_lifecycle_artifacts')
        assert 'company_lifecycle_artifacts' in inspect(engine).get_table_names()
        command.downgrade(cfg,'116_company_readiness_evidence');command.upgrade(cfg,'117_company_lifecycle_artifacts')
        raw=b'%PDF-1.4\nfixture\n%%EOF'
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO company_lifecycle_artifacts (id,lifecycle_event_id,member_id,artifact_kind,format_hint,raw_bytes,inspection_json,created_at) VALUES ('e','fixture','fixture','SUBMISSION_RECEIPT','pdf',:raw,'{}','2026-11-16')"),{'raw':raw})
        with pytest.raises(RuntimeError,match='Cannot discard'):
            command.downgrade(cfg,'116_company_readiness_evidence')
        with engine.connect() as conn:assert conn.scalar(text('SELECT raw_bytes FROM company_lifecycle_artifacts'))==raw
    finally:
        engine.dispose();invalidate_settings_cache()
