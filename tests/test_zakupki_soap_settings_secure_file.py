import pytest
from src.modules.tender_operator_agent_demo import settings as module


def test_secure_token_file_loaded_without_exposing_value(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(module.Path, "home", lambda: tmp_path)
    for key in ("ZAKUPKI_GOV_RU_SOAP_TOKEN", "ZAKUPKI_GOV_RU_SOAP_ENABLED", "ZAKUPKI_GOV_RU_SOAP_TOKEN_OWNER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(module, "_ENV_FILES_SEEDED", False)
    folder = tmp_path / ".config/arvectum"
    folder.mkdir(parents=True)
    config = folder / "r3-soap-token.env"
    config.write_text("ZAKUPKI_GOV_RU_SOAP_TOKEN=sample-test-token\nZAKUPKI_GOV_RU_SOAP_TOKEN_OWNER=individual\n")
    config.chmod(0o600)
    module._seed_secure_soap_file()
    result = module.ZakupkiSoapSettings.from_env()
    assert result.enabled and result.configured and result.token == "sample-test-token"


def test_secure_token_rejects_permissive_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(module, "_ENV_FILES_SEEDED", False)
    folder = tmp_path / ".config/arvectum"
    folder.mkdir(parents=True)
    config = folder / "r3-soap-token.env"
    config.write_text("ZAKUPKI_GOV_RU_SOAP_TOKEN=sample-test-token\n")
    config.chmod(0o644)
    with pytest.raises(ValueError, match="chmod 600"):
        module._seed_secure_soap_file()
