import pytest

from scripts.ops import apr07_analysis_window as cli


def test_requires_explicit_separate_connection(monkeypatch, capsys):
    monkeypatch.delenv(cli.DSN_ENV, raising=False)
    monkeypatch.setenv('AI_CORP_DATABASE_URL', 'postgresql+psycopg://private:secret@server/db')
    assert cli.main([]) == 2
    out = capsys.readouterr()
    assert out.out == '' and 'secret' not in out.err
    assert cli.DSN_ENV in out.err


@pytest.mark.parametrize('value', [
    'sqlite:///test.db', 'postgresql+psycopg://user@host/db',
    'postgresql+psycopg://user@/db?host=localhost',
    'postgresql+psycopg://user@/db?host=/tmp&hostaddr=192.0.2.1',
    'postgresql+psycopg://user@/db?host=/tmp&options=-csearch_path%3Dother',
    'postgresql+psycopg://user@/db?host=/not/a/socket/path',
])
def test_reject_nonlocal_and_implicit_or_unsafe_urls(value):
    with pytest.raises(ValueError):
        cli.operator_url(value)


def test_explicit_socket_url(tmp_path):
    url = cli.operator_url(f'postgresql+psycopg://observer@/test?host={tmp_path}&port=5432')
    assert url.username == 'observer' and url.query['host'] == str(tmp_path)


def test_failure_does_not_expose_credentials(monkeypatch, capsys):
    monkeypatch.setenv(cli.DSN_ENV, 'private-value')
    def fail(*args, **kwargs):
        raise ValueError('private-value secret')
    monkeypatch.setattr(cli, 'snapshot', fail)
    assert cli.main([]) == 2
    out = capsys.readouterr()
    assert out.out == '' and 'private-value' not in out.err and 'secret' not in out.err


@pytest.mark.parametrize('name', ['PGHOSTADDR', 'PGSERVICE', 'PGOPTIONS'])
def test_reject_implicit_libpq_destination_or_options(tmp_path, monkeypatch, name):
    monkeypatch.setenv(name, 'unsafe-override')
    with pytest.raises(ValueError):
        cli.operator_url(f'postgresql+psycopg://observer@/test?host={tmp_path}')
