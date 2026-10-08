import json

from scripts.diagnose_zakupki_soap import run_diagnostics, save_diagnostics
from src.modules.tender_operator_agent_demo.procurement_schemas import DocsArchiveResult
from src.modules.tender_operator_agent_demo.settings import ZakupkiSoapSettings


def _settings(token: str = "test-token-value-not-real") -> ZakupkiSoapSettings:
    return ZakupkiSoapSettings(enabled=True, token=token, token_owner="individual")


def test_diagnostics_sanitizes_token_and_reports_no_archive(monkeypatch, tmp_path):
    from scripts import diagnose_zakupki_soap as module

    diagnostics_root = tmp_path / "zakupki_soap_diagnostics"
    monkeypatch.chdir(tmp_path)

    class FakeClient:
        def __init__(self, _settings):
            pass

        def probe_xsd(self):
            return {"status": "ok"}

        def get_docs_by_reestr_number(self, _reestr_number):
            return DocsArchiveResult(
                request_id="req-001",
                ref_id=None,
                archive_url=None,
                status="no_archive_url",
                warnings=["archiveUrl not found"],
                safe_diagnostic={"archive_url_present": False},
            )

    monkeypatch.setattr(module, "ZakupkiSoapClient", FakeClient)
    payload = run_diagnostics(
        settings=_settings("secret-token-value"),
        reestr_number="0888200000224000038",
        check_xsd=True,
        download_archive=False,
    )
    path = save_diagnostics(payload)

    assert payload["token_present"] is True
    assert payload["response_kind"] == "no_archive_url"
    assert payload["eis_proxy_disabled"] is True
    assert payload["client_trust_env"] is False
    assert "secret-token-value" not in json.dumps(payload, ensure_ascii=False)
    assert path.exists()


def test_diagnostics_reports_downloaded_archive(monkeypatch, tmp_path):
    from scripts import diagnose_zakupki_soap as module
    from src.modules.tender_operator_agent_demo.procurement_schemas import DownloadedAttachment

    monkeypatch.chdir(tmp_path)

    class FakeClient:
        def __init__(self, _settings):
            pass

        def get_docs_by_reestr_number(self, _reestr_number):
            return DocsArchiveResult(
                request_id="req-002",
                ref_id="ref-002",
                archive_url="https://int44.zakupki.gov.ru/archive/demo.zip",
                status="completed",
                warnings=[],
                safe_diagnostic={"archive_url_present": True},
            )

        def download_archive(self, _archive_url, _target_dir):
            return DownloadedAttachment(
                file_name="demo.zip",
                stored_name="documentation-archive.zip",
                size_bytes=128,
                content_type="application/zip",
                source_url_host="int44.zakupki.gov.ru",
                source_url_path="/archive/demo.zip",
            )

    monkeypatch.setattr(module, "download_xml_referenced_attachments", lambda *_args: {"expected": 1, "downloaded": 1, "complete": True, "size_mismatches": [], "errors": []})
    monkeypatch.setattr(module, "ZakupkiSoapClient", FakeClient)
    payload = run_diagnostics(
        settings=_settings(),
        reestr_number="0888200000224000038",
        download_archive=True,
    )

    assert payload["archive_url_present"] is True
    assert payload["download_status"] == "downloaded"
    assert payload["archive_url_summary"]["host"] == "int44.zakupki.gov.ru"


def test_diagnostics_marks_env_proxy_detected(monkeypatch, tmp_path):
    from scripts import diagnose_zakupki_soap as module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HTTP_PROXY", "http://user:pass@proxy.example:8080")

    class FakeClient:
        def __init__(self, _settings):
            pass

        def get_docs_by_reestr_number(self, _reestr_number):
            return DocsArchiveResult(
                request_id="req-003",
                ref_id=None,
                archive_url=None,
                status="no_archive_url",
                warnings=[],
                safe_diagnostic={},
            )

    monkeypatch.setattr(module, "ZakupkiSoapClient", FakeClient)
    payload = run_diagnostics(settings=_settings(), reestr_number="0888200000224000038")

    assert payload["env_proxy_detected"] is True
    assert payload["route_mode"] == "direct_for_eis"
    assert "user:pass" not in json.dumps(payload, ensure_ascii=False)


def test_diagnostics_includes_route_check(monkeypatch, tmp_path):
    from scripts import diagnose_zakupki_soap as module

    monkeypatch.chdir(tmp_path)

    class FakeClient:
        def __init__(self, _settings):
            pass

        def get_docs_by_reestr_number(self, _reestr_number):
            return DocsArchiveResult(
                request_id="req-004",
                ref_id=None,
                archive_url=None,
                status="no_archive_url",
                warnings=[],
                safe_diagnostic={},
            )

        def probe_xsd(self):
            return {"status": "ok"}

    monkeypatch.setattr(module, "ZakupkiSoapClient", FakeClient)
    monkeypatch.setattr(module, "_run_route_check", lambda _settings: {"dns_status": "ok", "tcp_status": "ok", "tls_status": "ok", "http_get_status": "ok"})
    payload = run_diagnostics(settings=_settings(), reestr_number="0888200000224000038", route_check=True)

    assert payload["route_check"]["dns_status"] == "ok"
    assert payload["route_check"]["tls_status"] == "ok"


def test_223fz_org_region_routes_ri223_and_date(monkeypatch):
    from scripts import diagnose_zakupki_soap as module
    seen = {}

    class FakeClient:
        def __init__(self, _settings):
            pass

        def get_docs_by_org_region(self, region, exact_date, document_type, *, subsystem_type):
            seen.update(region=region, exact_date=exact_date, document_type=document_type, subsystem_type=subsystem_type)
            return DocsArchiveResult(request_id="ri223-test", ref_id="ok", archive_url=None, status="no_data")

    monkeypatch.setattr(module, "ZakupkiSoapClient", FakeClient)
    result = run_diagnostics(
        settings=_settings(), reestr_number="32616445866",
        method="getDocsByOrgRegion", subsystem_type="RI223",
        org_region="77", exact_date="2026-10-07", document_type="purchaseNotice",
    )
    assert seen == dict(region="77", exact_date="2026-10-07", document_type="purchaseNotice", subsystem_type="RI223")
    assert result["selection"]["subsystem_type"] == "RI223"


def test_download_ri223_documents_xml_and_dedupe(monkeypatch, tmp_path):
    import zipfile
    from scripts import diagnose_zakupki_soap as module
    archive = tmp_path / "ri223.zip"
    xml = (
        '<purchaseNotice><attachments><document><contentUid>aaa</contentUid>'
        '<fileName>project.docx</fileName><url>https://zakupki.gov.ru/223/filestore/public/file.html?uid=aaa</url>'
        '</document></attachments></purchaseNotice>'
    )
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("purchaseNotice_1.xml", xml)
        output.writestr("purchaseNotice_2.xml", xml)
    from types import SimpleNamespace
    captured = []

    def fake_download(attachments, **kwargs):
        captured.extend(attachments)
        return SimpleNamespace(saved=[SimpleNamespace(name=a.name, size_bytes=0) for a in attachments], skipped=[])

    monkeypatch.setattr(module, "download_procurement_attachments", fake_download)
    result = module.download_xml_referenced_attachments(archive, tmp_path / "downloaded")
    assert result["expected"] == result["downloaded"] == 1
    assert result["complete"] is True
    assert captured[0].attachment_id == "aaa"
    assert captured[0].name == "project.docx"
