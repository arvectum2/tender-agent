"""ZIP archives never bypass path limits or crash the intake workflow."""

from __future__ import annotations

import io
import stat
import zipfile

from src.modules.tender_operator_agent_demo.operator_archive_intake import (
    read_operator_zip_documents,
)


def _archive(path, members, *, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in members:
            archive.writestr(name, content)
    return path


def _run(path, **kwargs):
    return read_operator_zip_documents(
        path, "FILE-01",
        allowed_extensions={".txt", ".docx", ".zip"},
        max_entries=kwargs.get("max_entries", 8),
        max_total_bytes=kwargs.get("max_total_bytes", 2000),
        extract_text=lambda name, raw: (raw.decode("utf-8"), [], "extracted"),
        detect_role=lambda name: "technical_spec",
    )


def test_safe_zip_file_preserves_original_bytes_and_document_type(tmp_path):
    path = _archive(tmp_path / "supplier.zip", [("spec.txt", b"real contract terms")])
    files = _run(path)
    assert len(files) == 1
    assert files[0].text == "real contract terms"
    assert files[0].file_id == "FILE-01-ZIP-01"
    assert files[0].source == "zip"
    assert files[0].raw_content == b"real contract terms"


def test_posix_and_windows_traversal_rejected_without_reading(tmp_path):
    path = _archive(tmp_path / "untrusted.zip", [
        ("../../other.txt", b"bad"), ("..\\secret.txt", b"bad"),
        ("C:\\Users\\secret.txt", b"bad"), ("ok.txt", b"allowed"),
    ])
    files = _run(path)
    assert len(files) == 4
    assert [f.extracted_text_available for f in files] == [False, False, False, True]
    assert all(f.raw_content is None for f in files[:3])


def test_duplicate_entry_is_not_implicitly_overwritten(tmp_path):
    path = _archive(tmp_path / "duplicates.zip", [
        ("part.txt", b"first"), ("PART.TXT", b"second"),
    ])
    files = _run(path)
    assert files[0].text == "first"
    assert files[1].text is None
    assert "duplicated" in files[1].warnings[0]


def test_entry_count_and_unpacked_size_fail_closed(tmp_path):
    path = _archive(tmp_path / "many.zip", [("a.txt", b"aaa"), ("b.txt", b"bbb")])
    assert _run(path, max_entries=1)[0].extracted_text_available is False
    assert "too many" in _run(path, max_entries=1)[0].warnings[0]
    assert "size limit" in _run(path, max_total_bytes=4)[0].warnings[0]


def test_unsafe_symlink_metadata_is_rejected(tmp_path):
    path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link.txt")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, b"../../secret")
    assert not _run(path)[0].extracted_text_available


def test_corrupt_archive_returns_safe_warning(tmp_path):
    path = tmp_path / "corrupt.zip"
    path.write_bytes(b"not a ZIP")
    files = _run(path)
    assert len(files) == 1 and "safely" in files[0].warnings[0]


def test_nested_zip_is_ignored_not_recursively_expanded(tmp_path):
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as z:
        z.writestr("hidden.txt", "private")
    path = _archive(tmp_path / "nested.zip", [("nested.zip", nested.getvalue())])
    assert _run(path) == []


def test_signed_archive_excludes_signing_html_but_keeps_official_pdf(tmp_path):
    path = _archive(tmp_path / "source.zip", [
        ("Обоснование начальной цены контракта.pdf", b"original-nmck"),
        ("Лист подписания условий контракта.html", b"non-substantive-signing-receipt"),
        ("Подпись_ведомства.sign", b"detached-sign"),
        ("Технические условия.html", b"official-document"),
    ])
    docs = read_operator_zip_documents(
        path, "FILE-17", allowed_extensions={".pdf", ".html", ".sign"},
        max_entries=8, max_total_bytes=1024,
        extract_text=lambda name, raw: (raw.decode(), [], "extracted"),
        detect_role=lambda name: "supporting",
    )
    assert [v.display_name.split(" :: ")[-1] for v in docs] == [
        "Обоснование начальной цены контракта.pdf",
        "Технические условия.html",
    ]


def test_genuine_signed_eis_document_roles_keep_nmck_and_security_out_of_draft():
    from src.modules.procurement_analysis.document_roles import detect_document_role
    assert detect_document_role("Обоснование начальной (максимальной) цены контракта от 30.03.2026.pdf") == "supporting"
    assert detect_document_role("Определение начальной (максимальной) цены контракта (Расчет).pdf") == "supporting"
    assert detect_document_role("Обеспечение исполнения государственного контракта.docx") == "supporting"
    assert detect_document_role("Умный контракт_создание и развитие информационных систем.docx") == "contract_draft"
    assert detect_document_role("САЙТ_ТЗ_на_ДОРАБОТКУ_2026 ИТОГ.docx") == "technical_spec"
