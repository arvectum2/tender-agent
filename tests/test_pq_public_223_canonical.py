import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_public_223_canonical import canonicalize


def _set_up(tmp_path: Path):
    source = tmp_path / "staged"
    root = source / "32615969197"
    root.mkdir(parents=True)
    raw = b"Original primary public EIS document"
    digest = hashlib.sha256(raw).hexdigest()
    records = []
    for number in range(2):
        name = f"rev{number}.docx"
        (root / name).write_bytes(raw)
        records.append({
            "registry_number": "32615969197",
            "status": "staged_sha256_verified_not_yet_indexed",
            "stored_name": name,
            "member_sha256": digest,
            "source_page_sha256": "c"*64,
            "source_archive_sha256": str(number)*64,
        })
    (source / "public-members-manifest.json").write_text(json.dumps({
        "schema_version": "pq-public-eis-zip-members/1", "records": records}))
    return source, digest


def test_dedup_revisions_and_resume(tmp_path: Path):
    source, digest = _set_up(tmp_path)
    output = tmp_path / "canonical"
    result = canonicalize(staged=source, output=output)
    assert result["unique_files"] == 1
    assert result["original_xml_binding_verified"] is False
    target = output / "32615969197" / (digest + ".docx")
    assert target.is_file()
    assert canonicalize(staged=source, output=output)["unique_files"] == 1
    assert len(list((output / "32615969197").glob("*.docx"))) == 1


def test_changed_member_rejected(tmp_path: Path):
    source, _ = _set_up(tmp_path)
    (source / "32615969197" / "rev0.docx").write_bytes(b"modified")
    with pytest.raises(ValueError, match="checksum"):
        canonicalize(staged=source, output=tmp_path / "canonical")
