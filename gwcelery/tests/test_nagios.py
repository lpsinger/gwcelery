import subprocess
from unittest.mock import patch

import pytest

from .. import app
from .. import nagios

try:
    subprocess.check_call(['which', 'redis-server'])
except subprocess.CalledProcessError:
    HAS_REDIS = False
else:
    HAS_REDIS = True


@pytest.fixture
def unix_domain_socket(monkeypatch, socket_enabled, tmpdir):
    filename = str(tmpdir / 'redis.sock')
    monkeypatch.setenv('CELERY_BROKER_URL', 'redis+socket://' + filename)
    yield filename


@pytest.fixture
def redis(unix_domain_socket):
    with subprocess.Popen(['redis-server', '--port', '0',
                           '--unixsocket', unix_domain_socket,
                           '--unixsocketperm', '700']) as p:
        yield p
        p.terminate()


# Note: the names of these unit tests must be very short because there is a
# very strict limit on the length of a Unix domain socket path.
# See https://unix.stackexchange.com/questions/367008


@patch('gwcelery.app.connection', side_effect=RuntimeError)
def test0(mock_connection, capsys):
    """Test that we generate the correct message when there is an unexpected
    exception."""
    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.UNKNOWN
    out, err = capsys.readouterr()
    assert out.startswith('UNKNOWN: Unexpected error')


def test1(capsys, unix_domain_socket):
    """Test that we generate the correct message when the broker is not
    running."""
    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert out.startswith('CRITICAL: No connection to broker')


@pytest.mark.skipif(not HAS_REDIS, reason='redis-server is not installed')
def test2(capsys, redis):
    """Test that we generate the correct message when the broker is running but
    none of the workers are."""
    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert out.startswith('CRITICAL: Not all expected queues are active')
