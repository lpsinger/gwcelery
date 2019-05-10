from distutils.spawn import find_executable
from unittest.mock import Mock

import pytest

from .. import app
from ..tools import nagios


def test_nagios_unknown_error(monkeypatch, capsys):
    """Test that we generate the correct message when there is an unexpected
    exception."""
    monkeypatch.setattr('gwcelery.app.connection',
                        Mock(side_effect=RuntimeError))

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.UNKNOWN
    out, err = capsys.readouterr()
    assert 'UNKNOWN: Unexpected error' in out


def test_nagios(capsys, monkeypatch, socket_enabled, starter):
    mock_lvalert_client = Mock()
    monkeypatch.setattr('sleek_lvalert.LVAlertClient', mock_lvalert_client)
    unix_socket = app.conf['broker_url'].replace('redis+socket://', '')

    # no broker

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
        args=(['gwcelery', 'worker', '-l', 'info', '--pool', 'solo',
               '-Q', 'celery,exttrig,openmp,superevent,voevent'],),
        target=app.start, timeout=10, magic_words=b'ready.')

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: Not all expected tasks are active' in out

    # tasks, no LVAlert nodes

    monkeypatch.setattr('gwcelery.tools.nagios.get_active_tasks',
                        lambda _: nagios.get_expected_tasks(app))
    mock_lvalert_client.configure_mock(**{
        'return_value.get_subscriptions.return_value': {}})

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: Not all lvalert nodes are subscribed' in out

    # tasks, too many LVAlert nodes

    mock_lvalert_client.configure_mock(**{
        'return_value.get_subscriptions.return_value':
        nagios.get_expected_lvalert_nodes() | {'foobar'}})

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: Too many lvalert nodes are subscribed' in out

    # LVAlert nodes present, no VOEvent broker peers

    mock_lvalert_client.configure_mock(**{
        'return_value.get_subscriptions.return_value':
        nagios.get_expected_lvalert_nodes()})

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: The VOEvent broker has no active connections' in out

    # VOEvent broker peers, no VOEvent receiver peers

    monkeypatch.setattr(
        'celery.app.control.Inspect.stats',
        Mock(return_value={'foo': {'voevent-broker-peers': ['127.0.0.1']}}))

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.CRITICAL
    out, err = capsys.readouterr()
    assert 'CRITICAL: The VOEvent receiver has no active connections' in out

    # success

    monkeypatch.setattr(
        'celery.app.control.Inspect.stats',
        Mock(return_value={'foo': {'voevent-broker-peers': ['127.0.0.1'],
                                   'voevent-receiver-peers': ['127.0.0.1']}}))

    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'nagios'])
    assert excinfo.value.code == nagios.NagiosPluginStatus.OK
    out, err = capsys.readouterr()
    assert 'OK: Running normally' in out
