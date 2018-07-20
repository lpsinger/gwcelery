import json
import logging
import socket
import struct
from threading import Thread
from time import sleep
from unittest.mock import MagicMock, patch

from gcn.voeventclient import _recv_packet
import lxml.etree
import pkg_resources
import pytest

from ..tasks import gcn
from .. import app

logging.basicConfig(level=logging.INFO)

# Test data
with pkg_resources.resource_stream(
        __name__, 'data/lvalert_voevent.json') as f:
    lvalert = json.load(f)
voevent = lvalert['object']['text']


@pytest.fixture
def broker_thread(monkeypatch):
    queue = [b'foo', b'bar', b'bat']

    def lindex(key, index):
        assert key == gcn._queue_name
        try:
            return queue[index]
        except IndexError:
            return None

    def lpop(key):
        assert key == gcn._queue_name
        try:
            return queue.pop(0)
        except IndexError:
            return None

    # Decrease keepalive time so that we see keepalive packets frequently
    monkeypatch.setattr('gwcelery.tasks.gcn.KEEPALIVE_TIME', 1)
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.backend.client.lindex',
                        lindex, raising=False)
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.backend.client.lpop',
                        lpop, raising=False)

    monkeypatch.setattr('gwcelery.tasks.gcn.broker.is_aborted', lambda: False)
    thread = Thread(target=gcn.broker)
    thread.start()
    sleep(0.1)
    yield
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.is_aborted', lambda: True)
    thread.join()


@pytest.fixture
def wrong_remote_address():
    old = app.conf['gcn_broker_accept_addresses']
    app.conf['gcn_broker_accept_addresses'] = ['192.0.2.0']
    yield
    app.conf['gcn_broker_accept_addresses'] = old


@pytest.fixture
def connection_to_broker(broker_thread):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', 1, 0))
        sock.connect(('127.0.0.1', 53410))
        yield sock


@pytest.mark.enable_socket
def test_broker_aborted_before_accept(broker_thread, monkeypatch):
    """Test aborting the broker while it is still waiting for connections."""
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.is_aborted', lambda: True)


@pytest.mark.enable_socket
def test_broker_aborted_after_accept(connection_to_broker, monkeypatch):
    """Test aborting the broker after it has accepted a connection."""
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.is_aborted', lambda: True)


@pytest.mark.enable_socket
def test_broker_disconnected(connection_to_broker):
    """Test connection from a broker to a client that immediately closes the
    socket."""
    pass


@pytest.mark.enable_socket
def test_broker_wrong_address(capsys, wrong_remote_address,
                              connection_to_broker):
    """Test that the broker refuses connections from the wrong IP address."""
    assert connection_to_broker.recv(1) == b''


@pytest.mark.enable_socket
def test_broker(connection_to_broker, broker_thread):
    """Test receiving packets from the broker."""
    connection_to_broker.settimeout(2.0)
    packets = [_recv_packet(connection_to_broker) for _ in range(4)]
    assert packets[:3] == [b'foo', b'bar', b'bat']
    assert b'iamalive' in packets[3]


def test_send(monkeypatch):
    mock_rpush = MagicMock()
    monkeypatch.setattr('gwcelery.tasks.gcn.broker.backend.client.rpush',
                        mock_rpush, raising=False)
    gcn.send(b'foo')
    mock_rpush.assert_called_once_with(gcn._queue_name, b'foo')


@pytest.mark.enable_socket
def test_listen(monkeypatch):
    """Test that the listen task would correctly launch gcn.listen()."""
    mock_gcn_listen = MagicMock()
    monkeypatch.setattr('gcn.listen', mock_gcn_listen)
    gcn.listen.run()
    mock_gcn_listen.assert_called_once()


def fake_gcn(notice_type):
    # Check the real GCN notice, which is valid.
    payload = pkg_resources.resource_string(
        __name__, 'data/G298048-1-Initial.gcn.xml')
    root = lxml.etree.fromstring(payload)
    notice_type = str(int(notice_type))
    root.find(".//Param[@name='Packet_Type']").attrib['value'] = notice_type
    return lxml.etree.tostring(root), root


def test_unrecognized_notice_type(caplog):
    """Test handling an unrecognized (enum not defined) notice type."""
    caplog.set_level(logging.WARNING)
    gcn.handler.dispatch(*fake_gcn(10000))
    record, = caplog.records
    assert record.message == 'ignoring unrecognized key: 10000'


def test_unregistered_notice_type(caplog):
    """Test handling an unregistered notice type."""
    caplog.set_level(logging.WARNING)
    gcn.handler.dispatch(*fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
    record, = caplog.records
    assert record.message == ('ignoring unrecognized key: '
                              '<NoticeType.SWIFT_UVOT_POS_NACK: 89>')


@pytest.fixture
def reset_handlers():
    old_handler = dict(gcn.handler)
    gcn.handler.clear()
    yield
    gcn.handler.update(old_handler)


def test_registered_notice_type(reset_handlers):
    @gcn.handler(gcn.NoticeType.AGILE_POINTDIR, gcn.NoticeType.AGILE_TRANS)
    def agile_handler(payload):
        pass

    with patch.object(agile_handler, 'run') as mock_run:
        gcn.handler.dispatch(*fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
        mock_run.assert_not_called()
        gcn.handler.dispatch(*fake_gcn(gcn.NoticeType.AGILE_POINTDIR))
        mock_run.assert_called_once()
