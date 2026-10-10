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
