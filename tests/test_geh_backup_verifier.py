from pathlib import Path
from unittest.mock import Mock
import pytest
from scripts.research import run_gpb_archive_import as module

@pytest.fixture
def archive(tmp_path):
    p=tmp_path/'backup.partial'; p.write_bytes(b'PGDMP fixture'); return p

def test_verifies_source_and_streams_archive_without_restore(monkeypatch,archive):
    cmd=Mock(return_value=b'7694400479046774822\n'); monkeypatch.setattr(module,'command',cmd)
    def execute(args,**kwargs):
        assert args==['docker','exec','-i',module.DB,'pg_restore','--list']
        assert kwargs['stdin'].read()==archive.read_bytes()
        return Mock(returncode=0,stdout=b'123 TABLE DATA sample')
    monkeypatch.setattr(module.subprocess,'run',execute); module.verify_ta_archive(archive)
    assert 'pg_control_system()' in cmd.call_args.args[0][-1]
    assert archive.exists()

@pytest.mark.parametrize('identity,rc,stdout',[(b'other',0,b'TABLE DATA'),(b'7694400479046774822',1,b'TABLE DATA'),(b'7694400479046774822',0,b'empty')])
def test_fail_closed(monkeypatch,archive,identity,rc,stdout):
    monkeypatch.setattr(module,'command',Mock(return_value=identity));run=Mock(return_value=Mock(returncode=rc,stdout=stdout));monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(RuntimeError):module.verify_ta_archive(archive)
    if identity==b'other':run.assert_not_called()
    assert archive.exists()

def test_symlink_or_empty_rejected(tmp_path,archive):
    link=tmp_path/'link';link.symlink_to(archive)
    with pytest.raises(ValueError):module.verify_ta_archive(link)
    archive.write_bytes(b'')
    with pytest.raises(ValueError):module.verify_ta_archive(archive)
