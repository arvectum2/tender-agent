from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest

from src.modules.market_intelligence.pq_dp_fallback import pdf_text_fallback


def test_pdf_native_fallback(tmp_path: Path):
    file = tmp_path / "original.pdf"
    file.write_bytes(b"%PDF-1.7")
    with patch("src.modules.market_intelligence.pq_dp_fallback.subprocess.run",
               return_value=SimpleNamespace(returncode=0, stdout=b"STATCOM original technical text")):
        result = pdf_text_fallback(file)
    assert result["status"] == "extracted"
    assert result["characters"] == 30


def test_non_pdf_rejected(tmp_path: Path):
    file = tmp_path / "bad.txt"
    file.write_text("test")
    with pytest.raises(ValueError):
        pdf_text_fallback(file)
