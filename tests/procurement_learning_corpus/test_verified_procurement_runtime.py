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


def test_existing_prod_db_name_is_not_repurposed_as_tender_agent_db(tmp_path):
    owner, platform = owner_files(tmp_path)
    owner.write_text(
        owner.read_text().replace("PROD_DB_NAME=arvectum\n", "PROD_DB_NAME=separate_business_db\n")
    )
    owner.chmod(0o600)
    result = build_existing_environment(
        owner_config=owner, platform_config=platform,
        owner_uid=os.getuid(), inherited={},
        canonical_password_resolver=lambda: "different_canonical_container_password",
    )
    assert make_url(result["AI_CORP_DATABASE_URL"]).password == "different_canonical_container_password"
    assert make_url(result["AI_CORP_DATABASE_URL"]).database == "arvectum"
    assert "PROD_DB_NAME" not in result


def test_missing_existing_database_role_is_blocked(tmp_path):
    owner, platform = owner_files(tmp_path)
    owner.write_text(owner.read_text().replace("PROD_DB_USER=fake_operator\n", ""))
    with pytest.raises(RuntimeGateError, match="role credentials missing"):
        build_existing_environment(
            owner_config=owner, platform_config=platform, owner_uid=os.getuid()
        )


def test_no_credential_values_ever_logged(capsys,tmp_path):
    result=invoke(tmp_path)
    assert result["AI_CORP_DATABASE_URL"]
    assert not capsys.readouterr().out



def test_read_only_canonical_db_doctor_checks_real_identity(monkeypatch):
    from unittest.mock import MagicMock

    from scripts.runtime import verified_procurement_runtime as runtime

    connection = MagicMock()
    connection.scalar.side_effect = ["arvectum", True]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(runtime, "create_engine", lambda *args, **kwargs: engine)
    runtime.verify_actual_canonical_db("postgresql+psycopg://localhost/arvectum")
    assert connection.scalar.call_count == 2
    engine.dispose.assert_called_once()


def test_doctor_rejects_wrong_real_database_without_claiming_success(monkeypatch):
    from unittest.mock import MagicMock

    from scripts.runtime import verified_procurement_runtime as runtime

    connection = MagicMock()
    connection.scalar.side_effect = ["unrelated_other_database", True]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(runtime, "create_engine", lambda *args, **kwargs: engine)
    with pytest.raises(RuntimeGateError, match="not the canonical"):
        runtime.verify_actual_canonical_db("postgresql+psycopg://localhost/other")
    engine.dispose.assert_called_once()



def test_matching_db_uses_existing_owner_role_secret_not_other_credential_source(tmp_path):
    owner, platform = owner_files(tmp_path)
    result = build_existing_environment(
        owner_config=owner, platform_config=platform,
        owner_uid=os.getuid(), inherited={},
        canonical_password_resolver=lambda: pytest.fail("must not read other credential source"),
    )
    assert make_url(result["AI_CORP_DATABASE_URL"]).password == "fake_not_a_password"


def test_missing_canonical_container_secret_fails_closed(tmp_path):
    owner, platform = owner_files(tmp_path)
    owner.write_text(owner.read_text().replace("PROD_DB_NAME=arvectum",
                                               "PROD_DB_NAME=elsewhere"))
    owner.chmod(0o600)
    with pytest.raises(RuntimeGateError, match="password unavailable"):
        build_existing_environment(
            owner_config=owner, platform_config=platform,
            owner_uid=os.getuid(), inherited={},
            canonical_password_resolver=lambda: None,
        )


def test_canonical_container_credential_is_not_logged(monkeypatch,capsys):
    from types import SimpleNamespace

    from scripts.runtime import verified_procurement_runtime as runtime
    seen = []
    def read(*args, **kwargs):
        seen.append((args,kwargs))
        return SimpleNamespace(
            stdout='["POSTGRES_USER=arvectum", "POSTGRES_PASSWORD=fake_test_container_secret"]',
            stderr="", returncode=0,
        )
    monkeypatch.setattr(runtime.subprocess, "run", read)
    assert runtime._canonical_docker_password() == "fake_test_container_secret"
    assert seen and seen[0][1]["capture_output"] is True
    assert "fake_test_container_secret" not in capsys.readouterr().out


def test_missing_canonical_container_auth_does_not_expose_error_details(monkeypatch):
    from scripts.runtime import verified_procurement_runtime as runtime
    def broken(*args,**kwargs):
        raise RuntimeError("sensitive detail that must not escape")
    monkeypatch.setattr(runtime.subprocess,"run",broken)
    # A non-Docker Python/runtime bug should not be disguised as authentication.
    with pytest.raises(RuntimeError, match="sensitive detail"):
        runtime._canonical_docker_password()
