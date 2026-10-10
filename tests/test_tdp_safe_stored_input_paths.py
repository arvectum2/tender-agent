"""Operator source references must not escape their saved run directory."""
from __future__ import annotations

import pytest

from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)


def test_regular_stored_document_is_allowed(tmp_path):
    directory=tmp_path/'input'
    directory.mkdir()
    saved=directory/'01-spec.docx'
    saved.write_bytes(b'document')
    assert checked_original_input_path(directory,saved.name)==saved

@pytest.mark.parametrize('unsafe', ('../outside.xml','nested/other.xml', '..\\other.xml','', '.', '..', 'a:b.xml'))
def test_untrusted_metadata_filename_is_rejected(tmp_path,unsafe):
    directory=tmp_path/'input'
    directory.mkdir()
    with pytest.raises(ValueError):
        checked_original_input_path(directory,unsafe)

def test_symlinks_are_not_original_procurement_files(tmp_path):
    directory=tmp_path/'input'
    directory.mkdir()
    outside=tmp_path/'outside.xml'
    outside.write_text('private')
    inside=directory/'inside.xml'
    inside.write_text('local')
    for name,target in (('external.xml',outside),('internal.xml',inside)):
        (directory/name).symlink_to(target)
        with pytest.raises(ValueError):
            checked_original_input_path(directory,name)

def test_missing_or_directory_rejected(tmp_path):
    directory=tmp_path/'input'
    directory.mkdir()
    (directory/'nested').mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        checked_original_input_path(directory,'missing.xml')
    with pytest.raises(ValueError):
        checked_original_input_path(directory,'nested')


def test_getdocs_extracted_original_is_allowed_without_arbitrary_nested_paths(tmp_path):
    directory = tmp_path / "input"
    nested = directory / "extracted"
    nested.mkdir(parents=True)
    stored = nested / "01-notice.txt"
    stored.write_bytes(b"EIS original")
    assert checked_original_input_path(directory, "extracted/01-notice.txt") == stored.resolve()
    for unsafe in ("extracted/../outside.txt", "../extracted/01-notice.txt", "extracted/nested/file.txt", "extracted\\01-notice.txt", "extracted//01-notice.txt"):
        with pytest.raises(ValueError):
            checked_original_input_path(directory, unsafe)


def test_getdocs_extracted_symlink_parent_is_rejected(tmp_path):
    directory = tmp_path / "input"
    directory.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (other / "01-notice.txt").write_bytes(b"private")
    (directory / "extracted").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        checked_original_input_path(directory, "extracted/01-notice.txt")
