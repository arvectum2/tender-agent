"""APR-03 preflight, archive safety and isolated-deployment guardrails."""
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/production/runtime_ops.py"
spec = importlib.util.spec_from_file_location("production_runtime_ops", SCRIPT)
ops = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ops)


def env_file(tmp_path, **changes):
    entries = {
        "PROD_DOMAIN": "tender.example.com",
        "PROD_ACME_EMAIL": "ops@example.com",
        "PROD_DB_USER": "arvectum",
        "PROD_DB_NAME": "prod",
        "PROD_DB_PASSWORD": "A" * 40,
        "PROD_REDIS_PASSWORD": "B" * 40,
        "AI_CORP_PILOT_AUTH_USERNAME": "operator",
        "AI_CORP_PILOT_AUTH_PASSWORD": "C" * 40,
        "ZAKUPKI_GOV_RU_SOAP_TOKEN": "D" * 40,
    }
    entries.update(changes)
    path = tmp_path / "runtime-private.env"
    path.write_text("\n".join(f"{key}={value}" for key, value in entries.items()) + "\n")
    path.chmod(0o600)
    return path


def make_backup(tmp_path, *, archive_member="data/report.txt", tar_link=False):
    folder = tmp_path / "backup"
    folder.mkdir()
    (folder / "database.dump").write_bytes(b"PGDMPexample")
    with tarfile.open(folder / "files.tar.gz", "w:gz") as tar:
        info = tarfile.TarInfo(archive_member)
        if tar_link:
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        else:
            data = b"synthetic only"
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    manifest = {
        "format": "arvectum-apr03-backup-v1",
        "source_project": "arvectum-production",
        "application_commit": "a" * 40,
        "parts": {name: {"sha256": ops.digest(folder / name),
                         "bytes": (folder / name).stat().st_size}
                  for name in ("database.dump", "files.tar.gz")},
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return folder


def test_production_env_requires_external_mode_0600_and_distinct_secrets(tmp_path):
    source = env_file(tmp_path)
    assert ops.secure_env(source)["PROD_DOMAIN"] == "tender.example.com"
    source.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        ops.secure_env(source)
    with pytest.raises(ValueError, match="distinct"):
        ops.secure_env(env_file(tmp_path, PROD_REDIS_PASSWORD="A" * 40))
    with pytest.raises(ValueError, match="DNS"):
        ops.secure_env(env_file(tmp_path, PROD_DOMAIN="localhost"))


def test_preflight_rejects_unapproved_placeholders_and_auth_off(tmp_path):
    with pytest.raises(ValueError, match="random"):
        ops.secure_env(env_file(tmp_path, PROD_DB_PASSWORD="EXAMPLE"))
    with pytest.raises(ValueError, match="authentication"):
        ops.secure_env(env_file(tmp_path, AI_CORP_PILOT_AUTH_ENABLED="false"))
    with pytest.raises(ValueError, match="ACME"):
        ops.secure_env(env_file(tmp_path, PROD_ACME_EMAIL="demo@example.invalid"))


def test_backup_verify_checks_hash_length_and_archive_safety(tmp_path):
    good = make_backup(tmp_path)
    assert ops.verify(good)["source_project"] == "arvectum-production"
    (good / "database.dump").write_bytes(b"PGDMPtampered")
    with pytest.raises(ValueError, match="checksum"):
        ops.verify(good)


@pytest.mark.parametrize("member,link", [
    ("../../etc/passwd", False),
    ("/tmp/root", False),
    ("wrong-root/file", False),
    ("data/link", True),
])
def test_verify_rejects_unsafe_archive_members(tmp_path, member, link):
    bad = make_backup(tmp_path, archive_member=member, tar_link=link)
    with pytest.raises(ValueError, match="unsafe"):
        ops.verify(bad)


def test_production_network_and_human_gate_are_bounded():
    compose = (ROOT / "deploy/production/compose.yaml").read_text()
    caddy = (ROOT / "deploy/production/Caddyfile").read_text()
    assert "AI_CORP_TENDER_RESEARCH_JOB_BACKEND: redis" in compose
    assert "src.tender_research.rag.worker" in compose
    assert "healthcheck: {disable: true}" in compose  # The worker exposes no API port.
    assert "profiles: [public]" in compose
    assert 'ports: ["80:80", "443:443"]' in compose
    assert "private: {internal: true}" in compose
    assert 'AI_CORP_PILOT_AUTH_ENABLED: "true"' in compose
    assert 'AI_CORP_LLM_ALLOW_RAW_PARTNER_DATA: "false"' in compose
    assert "handle @allowed" in caddy
    assert 'respond "Not Found" 404' in caddy
    assert all(x not in compose for x in ('"5432:5432"', '"6379:6379"', '"8000:8000"'))


def test_restore_target_rejects_live_or_non_isolated_project_before_docker(tmp_path, monkeypatch):
    folder = make_backup(tmp_path)
    monkeypatch.setattr(ops, "common", lambda args: {})
    from argparse import Namespace
    args = Namespace(backup=folder, project="arvectum-production", revision="a" * 40)
    with pytest.raises(ValueError, match="distinct"):
        ops.restore(args)
    args.project = "arvectum-restore-test"
    args.revision = "b" * 40
    with pytest.raises(ValueError, match="exact application commit"):
        ops.restore(args)


def test_doctor_fails_closed_when_runtime_services_missing(monkeypatch, capsys):
    from argparse import Namespace
    from types import SimpleNamespace

    monkeypatch.setattr(ops, "common", lambda args: {})
    monkeypatch.setattr(
        ops, "compose",
        lambda args, *command, **kwargs: SimpleNamespace(stdout=b""),
    )
    with pytest.raises(ValueError, match="not healthy"):
        ops.doctor(Namespace())
    result = json.loads(capsys.readouterr().out)
    assert result["healthy"] is False
    assert set(result["services"]) == {"db", "redis", "api", "worker"}
    assert all(not item["running"] for item in result["services"].values())


@pytest.mark.parametrize("count,allowed", [(b"0\n", True), (b"1\n", False), (b"unknown\n", False)])
def test_recovery_gate_rejects_inflight_or_unknown_job_count(monkeypatch, count, allowed):
    from types import SimpleNamespace

    monkeypatch.setattr(
        ops, "compose",
        lambda *args, **kwargs: SimpleNamespace(stdout=count),
    )
    if allowed:
        ops.assert_no_inflight_tender_jobs(None, {})
    else:
        with pytest.raises(ValueError):
            ops.assert_no_inflight_tender_jobs(None, {})
