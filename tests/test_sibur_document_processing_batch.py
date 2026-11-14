import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest

from scripts.research.process_sibur_document_batch import (
    require_prewrite,
    select_batch,
    verified_bytes,
)


def test_verify_original_structure_and_sha(tmp_path):
    p = tmp_path / "original.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", "<document/>")
    assert verified_bytes(p, hashlib.sha256(p.read_bytes()).hexdigest()) == p.read_bytes()
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_bytes(p, "invalid")
    q = tmp_path / "invalid.xlsx"
    q.write_bytes(p.read_bytes())
    with pytest.raises(ValueError, match="OOXML"):
        verified_bytes(q, hashlib.sha256(q.read_bytes()).hexdigest())


def test_batch_keeps_priority_and_resumes(tmp_path):
    rows = {
        "a": {"sha256": "a", "bytes": 1, "references": [{"external_id": "other"}]},
        "b": {"sha256": "b", "bytes": 10, "references": [{"external_id": "priority"}]},
    }
    assert [r["sha256"] for r in select_batch(tmp_path, rows, {"priority"}, "extract", 2, 5)] == ["b", "a"]
    (tmp_path / "b.dp-result.json").write_text(json.dumps({
        "source_sha256": "b", "result": {"extraction_status": "extracted", "chunks": [1]}}))
    assert [r["sha256"] for r in select_batch(tmp_path, rows, {"priority"}, "extract", 2, 5)] == ["a"]
    assert [r["sha256"] for r in select_batch(tmp_path, rows, {"priority"}, "index", 2, 5)] == ["b"]
    (tmp_path / "persistent-pilot-b.json").write_text(json.dumps({"source_sha256": "b"}))
    assert not select_batch(tmp_path, rows, {"priority"}, "index", 2, 5)


def test_prewrite_requires_fresh_canonical_gate():
    now = datetime.now(UTC)
    gate = {"verified_at_utc": now.isoformat(), "status": "pass",
            "postgresql_mutated_by_preflight": False,
            "postgresql": {"database": "arvectum_data"}, "backup": {"sha256": "hash"}}
    require_prewrite(gate, now)
    with pytest.raises(ValueError, match="fresh"):
        require_prewrite(gate, now + timedelta(minutes=46))


def test_pdf_capture_signature_and_eof(tmp_path):
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.7\nbody\n%%EOF")
    assert verified_bytes(p, hashlib.sha256(p.read_bytes()).hexdigest()) == p.read_bytes()
    p.write_bytes(b"%PDF-1.7\ntruncated")
    with pytest.raises(ValueError, match="EOF"):
        verified_bytes(p, hashlib.sha256(p.read_bytes()).hexdigest())
