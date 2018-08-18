from distutils.spawn import find_executable
from unittest.mock import patch

import pytest

from .. import app
from .. import nagios


@patch('gwcelery.app.connection', side_effect=RuntimeError)
def test_nagios_unknown_error(mock_connection, capsys):
    """Test that we generate the correct message when there is an unexpected
    exception."""
    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.UNKNOWN
    out, err = capsys.readouterr()
    assert 'UNKNOWN: Unexpected error' in out


def test_nagios(capsys, monkeypatch, socket_enabled, starter, tmpdir):
    # no broker

    unix_socket = str(tmpdir / 'sock')
    monkeypatch.setenv('CELERY_BROKER_URL', 'redis+socket://' + unix_socket)

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: No connection to broker' in out

    # broker, no worker

    redis_server = find_executable('redis-server')
    if redis_server is None:
        pytest.skip('redis-server is not installed')
    starter.exec_process(
        [redis_server, '--port', '0', '--unixsocket', unix_socket,
         '--unixsocketperm', '700'], timeout=10,
        magic_words=b'The server is now ready to accept connections')

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: Not all expected queues are active' in out

    # worker, no tasks

    starter.python_process(
        args=(['gwcelery', 'worker', '-l', 'info',
               '-Q', 'celery,exttrig,openmp,superevent'],),
        target=app.start, timeout=10, magic_words=b'ready.')

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: Not all expected tasks are active' in out
