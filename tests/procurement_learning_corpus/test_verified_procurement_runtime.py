"""No new credentials; test guarded in-memory bootstrap using ONLY fake fixtures."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from scripts.runtime.verified_procurement_runtime import (
    RuntimeGateError,
    build_existing_environment,
)


def owner_files(tmp_path: Path, *, match: bool = True):
    owner=tmp_path/"owner.env"
    platform=tmp_path/"platform.env"
    owner.write_text(
        "PROD_DB_USER=fake_operator\n"
        "PROD_DB_PASSWORD=fake_not_a_password\n"
        "PROD_DB_NAME=arvectum\n"
        "AI_CORP_RAG_DATA_PLATFORM_API_KEY=fake-dp-key\n"
        "ZAKUPKI_GOV_RU_SOAP_TOKEN=fake-soap-unchanged\n"
    )
    platform.write_text("ARVECTUM_DATA_INTERNAL_API_KEY="
                        + ("fake-dp-key" if match else "other-key")+"\n")
    owner.chmod(0o600);platform.chmod(0o600)
    return owner,platform


def invoke(tmp_path, env=None, *, match=True):
    owner,platform=owner_files(tmp_path,match=match)
    return build_existing_environment(
        owner_config=owner,platform_config=platform,
        inherited={} if env is None else env,
        owner_uid=os.getuid(),
    )


def test_exact_canonical_db_and_platform_no_change_to_soap(tmp_path):
    result=invoke(tmp_path)
    db=make_url(result["AI_CORP_DATABASE_URL"])
    assert db.drivername=="postgresql+psycopg"
    assert db.database=="arvectum" and db.host=="127.0.0.1"
    assert db.port==55432 and db.username=="fake_operator"
    assert result["AI_CORP_RAG_DATA_PLATFORM_API_KEY"]=="fake-dp-key"
    assert "ZAKUPKI_GOV_RU_SOAP_TOKEN" not in result
    assert result["AI_CORP_ARVECTUM_DATA_DIR"].startswith("/Volumes/ArvectumSSD/")


def test_mismatched_platform_key_is_blocked(tmp_path):
    with pytest.raises(RuntimeGateError,match="keys do not match"):
        invoke(tmp_path,match=False)


def test_preexisting_wrong_or_sqlite_database_is_blocked(tmp_path):
    for value in ("sqlite:///ai_corporation.db",
                  "postgresql+psycopg://localhost/arvectum_other",
                  "postgresql+psycopg://remote.example/arvectum"):
        with pytest.raises(RuntimeGateError,match="nonlocal database"):
            invoke(tmp_path,{"AI_CORP_DATABASE_URL":value})


def test_preexisting_wrong_platform_key_is_blocked(tmp_path):
    with pytest.raises(RuntimeGateError,match="stale"):
        invoke(tmp_path,{"AI_CORP_RAG_DATA_PLATFORM_API_KEY":"not-our-runtime-key"})


def test_unprotected_file_is_not_a_source(tmp_path):
    owner,platform=owner_files(tmp_path)
    owner.chmod(0o644)
    with pytest.raises(RuntimeGateError,match="0600"):
        build_existing_environment(owner_config=owner,
                                    platform_config=platform,owner_uid=os.getuid())


def test_wrong_original_db_name_rejected(tmp_path):
    owner,platform=owner_files(tmp_path)
    owner.write_text(owner.read_text().replace("arvectum\n","fake_test_database\n"))
    with pytest.raises(RuntimeGateError,match="canonical PostgreSQL"):
        build_existing_environment(owner_config=owner,
                                    platform_config=platform,owner_uid=os.getuid())


def test_no_credential_values_ever_logged(capsys,tmp_path):
    result=invoke(tmp_path)
    assert result["AI_CORP_DATABASE_URL"]
    assert not capsys.readouterr().out
