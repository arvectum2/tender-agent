import subprocess

import pytest

from src.tender_research import ocr_adapter


def _tsv(confidence: str = '96.5') -> bytes:
    return ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            f"5\t1\t1\t1\t1\t1\t10\t20\t120\t30\t{confidence}\tТендер\n").encode()


def test_tesseract_adapter_preserves_coordinates_confidence_and_provenance(tmp_path, monkeypatch):
    image = tmp_path / 'scan.png'; image.write_bytes(b'fixture')
    executable = tmp_path / 'tesseract'; executable.write_bytes(b'fixture')
    monkeypatch.setattr(ocr_adapter, 'resolve_tesseract', lambda: executable)
    calls = []
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout=_tsv(), stderr=b'')
    monkeypatch.setattr(ocr_adapter.subprocess, 'run', fake_run)
    result = ocr_adapter.extract_image_with_tesseract(image)
    assert result is not None
    assert result.engine == 'tesseract'
    assert result.text == 'Тендер'
    assert result.mean_confidence == pytest.approx(96.5)
    assert result.needs_review is False
    assert result.words[0].left == 10 and result.words[0].top == 20
    assert calls[0][0] == [str(executable), str(image), 'stdout', '-l', 'rus+eng', 'tsv']
    assert calls[0][1]['timeout'] == ocr_adapter._TESSERACT_TIMEOUT_SECONDS


def test_low_confidence_is_explicit_review_signal(tmp_path, monkeypatch):
    image = tmp_path / 'scan.png'; image.write_bytes(b'fixture')
    executable = tmp_path / 'tesseract'; executable.write_bytes(b'fixture')
    monkeypatch.setattr(ocr_adapter, 'resolve_tesseract', lambda: executable)
    monkeypatch.setattr(ocr_adapter.subprocess, 'run', lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=_tsv('42'), stderr=b''))
    result = ocr_adapter.extract_image_with_tesseract(image)
    assert result is not None and result.needs_review is True


def test_missing_engine_and_malformed_output_fail_closed(tmp_path, monkeypatch):
    image = tmp_path / 'scan.png'; image.write_bytes(b'fixture')
    monkeypatch.setattr(ocr_adapter, 'resolve_tesseract', lambda: None)
    assert ocr_adapter.extract_image_with_tesseract(image) is None
    executable = tmp_path / 'tesseract'; executable.write_bytes(b'fixture')
    monkeypatch.setattr(ocr_adapter, 'resolve_tesseract', lambda: executable)
    monkeypatch.setattr(ocr_adapter.subprocess, 'run', lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=b'bad\nrow\n', stderr=b''))
    assert ocr_adapter.extract_image_with_tesseract(image) is None


def test_language_is_bounded(tmp_path):
    image = tmp_path / 'scan.png'; image.write_bytes(b'fixture')
    with pytest.raises(ValueError):
        ocr_adapter.extract_image_with_tesseract(image, language='../../evil')
