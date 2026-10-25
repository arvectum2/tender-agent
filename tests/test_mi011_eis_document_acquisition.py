from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pytest

from src.modules.market_intelligence.eis_attachment_acquisition import (
    acquire_223fz_eis_attachments,
)
from src.modules.market_intelligence.eis_zip_members import (
    stage_official_zip_children,
)
from src.tender_research.providers.public_44fz_search import (
    PublicDocumentLink,
    PublicSearchStatus,
    PublicTenderDetail,
)

OFFICIAL = (
    "https://zakupki.gov.ru/223/filestore/public/1.0/download/"
    "fz223/file.html?uid=ABCDEF1234567890ABCDEF1234567890"
)


def _zip(path: Path, content: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for filename, payload in content.items():
            package.writestr(filename, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _original_notice(tmp_path: Path) -> tuple[Path, str]:
    guid = "9a0e2f63-460d-42a5-aa06-c808427aeedc"
    xml = f"""<purchaseNoticeZKESMBO><body><item><purchaseNoticeZKESMBOData>
<registrationNumber>32313008364</registrationNumber><guid>{guid}</guid>
<attachments><document><fileName>Техническое задание.pdf</fileName></document></attachments>
</purchaseNoticeZKESMBOData></item></body></purchaseNoticeZKESMBO>""".encode()
    archive_path = tmp_path / "source.zip"
    return archive_path, _zip(archive_path, {"notice.xml": xml})


def _public_detail(**kwargs):
    return PublicTenderDetail(
        registry_number="32313008364", law_type="223fz",
        network_status=PublicSearchStatus.SUCCESS,
        common_info_html="<html>Официальная страница</html>",
        raw={"review_reasons": []},
        document_links=[
            PublicDocumentLink(title="ТЗ", file_name="Техническое задание.pdf", url=OFFICIAL),
            PublicDocumentLink(title="Не из исходного XML", file_name="Посторонний.pdf",
                               url=OFFICIAL.replace("ABCDEF1234567890", "1234567890ABCDEF")),
            PublicDocumentLink(title="Вне ЕИС", file_name="Техническое задание.pdf",
                               url="https://untrusted.example/evil.pdf"),
        ],
    )


def test_original_source_guid_to_public_file_through_shared_downloader(tmp_path: Path):
    zip_path, digest = _original_notice(tmp_path)
    called = []

    def transport(url, max_size):
        called.append(url)
        assert max_size == 1_000_000
        return b"%PDF-1.7\nvalid synthetic content", "application/pdf"

    result = acquire_223fz_eis_attachments(
        registry_number="32313008364", archive_path=zip_path,
        archive_sha256=digest, region="77", source_date="2026-10-25",
        target_dir=tmp_path / "downloads", max_attachments=2,
        max_file_bytes=1_000_000, max_total_bytes=2_000_000,
        fetch_detail=_public_detail, transport=transport,
    )
    assert result["status"] == "downloaded"
    assert result["downloaded_count"] == 1
    assert result["source_bound_candidate_count"] == 1
    assert result["public_pages_fetched"] == 1
    assert len(called) == 1 and called[0] == OFFICIAL
    assert result["records"][0]["detected_binary_format"] == "pdf"
    assert result["records"][0]["document_sha256"] == hashlib.sha256(
        b"%PDF-1.7\nvalid synthetic content"
    ).hexdigest()
    assert result["winner_verified"] is False
    assert result["signed_contract_price_verified"] is False
    assert result["records"][0]["data_platform_indexed"] is False
    serialized = json.dumps(result)
    assert "uid=" not in serialized
    assert "ABCDEF1234567890" not in serialized


def test_invalid_original_sha_fails_before_network(tmp_path: Path):
    path, _ = _original_notice(tmp_path)

    def forbidden(**kwargs):
        pytest.fail("Public page requested before original EIS SHA validation")

    with pytest.raises(ValueError, match="SHA-256"):
        acquire_223fz_eis_attachments(
            registry_number="32313008364", archive_path=path,
            archive_sha256="f" * 64, region="77", source_date="2026-10-25",
            target_dir=tmp_path / "downloads", fetch_detail=forbidden,
        )


def test_unsafe_budget_and_registry_number_rejected(tmp_path: Path):
    path, digest = _original_notice(tmp_path)
    for kwargs in ({"registry_number": "wrong"}, {"max_attachments": 41},
                   {"max_file_bytes": 0}, {"max_total_bytes": 500_000_000}):
        options = {
            "registry_number": "32313008364",
            "archive_path": path, "archive_sha256": digest, "region": "77",
            "source_date": "2026-10-25", "target_dir": tmp_path / "out",
            **kwargs,
        }
        with pytest.raises(ValueError):
            acquire_223fz_eis_attachments(**options)


def test_official_zip_stages_only_safe_one_level_documents(tmp_path: Path):
    path = tmp_path / "archive.zip"
    sha = _zip(path, {
        "ТЗ.pdf": b"%PDF-1.4\nPDF",
        "folder/таблица.xlsx": b"PK\x03\x04synthetic spreadsheet",
        "nested/working-drawings.7z": b"7z\xbc\xafopaque",
    })
    result = stage_official_zip_children(
        path, expected_parent_sha256=sha, target_dir=tmp_path / "staged",
    )
    assert result["staged_members"] == 2
    assert result["unparsed_opaque_members"] == 1
    assert result["listed_members"] == 3
    for row in result["records"]:
        if row["local_stored_name"]:
            saved = tmp_path / "staged" / row["local_stored_name"]
            assert saved.exists()
            assert hashlib.sha256(saved.read_bytes()).hexdigest() == row["member_sha256"]
    second = stage_official_zip_children(
        path, expected_parent_sha256=sha, target_dir=tmp_path / "staged",
    )
    assert second["staged_members"] == 2
    assert not (tmp_path / "staged/working-drawings.7z").exists()


def test_zip_member_path_traversal_denied(tmp_path: Path):
    path = tmp_path / "evil.zip"
    sha = _zip(path, {"../escape.pdf": b"%PDF content"})
    with pytest.raises(ValueError, match="Unsafe"):
        stage_official_zip_children(
            path, expected_parent_sha256=sha, target_dir=tmp_path / "output",
        )
    assert not (tmp_path / "escape.pdf").exists()


def test_zip_file_symlink_denied(tmp_path: Path):
    path = tmp_path / "symlink.zip"
    member = zipfile.ZipInfo("link.pdf")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(member, "../../secret")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Unsafe"):
        stage_official_zip_children(path, expected_parent_sha256=sha,
                                    target_dir=tmp_path / "out")


def test_zip_bomb_declared_ratio_denied(tmp_path: Path):
    path = tmp_path / "ratio.zip"
    sha = _zip(path, {"huge.txt": b"x" * (2 * 1024 * 1024)})
    with pytest.raises(ValueError, match="compression ratio"):
        stage_official_zip_children(path, expected_parent_sha256=sha,
                                    target_dir=tmp_path / "out")


def test_zip_parent_tamper_fails_closed(tmp_path: Path):
    path = tmp_path / "original.zip"
    sha = _zip(path, {"file.pdf": b"%PDF"})
    with pytest.raises(ValueError, match="parent SHA"):
        stage_official_zip_children(
            path, expected_parent_sha256="0" * 64,
            target_dir=tmp_path / "out",
        )
    assert sha != "0" * 64



def _original_44_notice(tmp_path: Path) -> tuple[Path, str]:
    number = "0373200026426000249"
    xml = f"""<export><epNotificationEF2020><commonInfo>
<purchaseNumber>{number}</purchaseNumber></commonInfo>
<attachments><attachmentInfo><fileName>Актуальное ТЗ.pdf</fileName></attachmentInfo></attachments>
</epNotificationEF2020></export>""".encode()
    path = tmp_path / "source44.zip"
    return path, _zip(path, {"official-notice.xml": xml})


def _44_active_detail(**kwargs):
    return PublicTenderDetail(
        registry_number="0373200026426000249", law_type="44fz",
        network_status=PublicSearchStatus.SUCCESS,
        documents_html="<html>Official revision 2</html>",
        raw={"document_revision_selection": {
            "status": "active_revision_selected",
            "requires_review": False,
            "active_revision": {"revision": 2},
        }},
        document_links=[
            PublicDocumentLink(
                file_name="Актуальное ТЗ.pdf",
                url=(
                    "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/"
                    "priz/file.html?uid=ABCDEF1234567890ABCDEF1234567890"
                ),
            ),
            PublicDocumentLink(
                file_name="Посторонний документ.pdf",
                url=(
                    "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/"
                    "priz/file.html?uid=1234567890ABCDEF1234567890ABCDEF"
                ),
            ),
        ],
    )


def test_44fz_current_revision_only_source_bound_original_file(tmp_path: Path):
    from src.modules.market_intelligence.eis_attachment_acquisition import (
        acquire_44fz_eis_attachments,
    )

    path, sha = _original_44_notice(tmp_path)
    seen = []

    def transport(url, limit):
        seen.append(url)
        return b"%PDF-1.7 verified original fixture", "application/pdf"

    result = acquire_44fz_eis_attachments(
        registry_number="0373200026426000249",
        archive_path=path, archive_sha256=sha, region="77",
        source_date="2026-10-25", target_dir=tmp_path / "download",
        fetch_detail=_44_active_detail, transport=transport,
    )
    assert result["downloaded_count"] == 1
    assert result["source_bound_candidate_count"] == 1
    assert result["active_revision"] == 2
    assert result["winner_verified"] is False
    assert len(seen) == 1
    assert "uid=" not in json.dumps(result)
    assert result["records"][0]["file_sha256"] == hashlib.sha256(
        b"%PDF-1.7 verified original fixture"
    ).hexdigest()


def test_44fz_ambiguous_active_revision_refuses_all_downloads(tmp_path: Path):
    from src.modules.market_intelligence.eis_attachment_acquisition import (
        acquire_44fz_eis_attachments,
    )

    path, sha = _original_44_notice(tmp_path)

    def ambiguous(**kwargs):
        d = _44_active_detail(**kwargs)
        d.raw["document_revision_selection"] = {
            "status": "revision_ambiguous", "requires_review": True,
        }
        return d

    result = acquire_44fz_eis_attachments(
        registry_number="0373200026426000249",
        archive_path=path, archive_sha256=sha, region="77",
        source_date="2026-10-25", target_dir=tmp_path / "download",
        fetch_detail=ambiguous, transport=lambda *args: pytest.fail("must not download"),
    )
    assert result["status"] == "active_revision_requires_review"
    assert result["downloaded_count"] == 0


def test_44fz_missing_primary_source_notice_rejects(tmp_path: Path):
    from src.modules.market_intelligence.eis_attachment_acquisition import (
        acquire_44fz_eis_attachments,
    )

    path, sha = _original_44_notice(tmp_path)
    with pytest.raises(ValueError, match="Original 44-FZ source notice"):
        acquire_44fz_eis_attachments(
            registry_number="0372200172326000015",
            archive_path=path, archive_sha256=sha, region="77",
            source_date="2026-10-25", target_dir=tmp_path / "download",
            fetch_detail=lambda **kwargs: pytest.fail("must not fetch public page"),
        )
