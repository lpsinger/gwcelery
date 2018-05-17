import json
import logging
import socket
from threading import Thread
from time import sleep
from unittest.mock import MagicMock, patch

import gcn
from gcn.voeventclient import _recv_packet
import lxml.etree
import pkg_resources
import pytest

from ..tasks.gcn import handler, listen, send
from .. import app

# Test data
with pkg_resources.resource_stream(
        __name__, 'data/lvalert_voevent.json') as f:
    lvalert = json.load(f)
voevent = lvalert['object']['text']


@pytest.fixture
def send_thread():
    thread = Thread(target=send, args=(voevent,))
    thread.daemon = True
    thread.start()
    sleep(1)
    yield thread
    thread.join()
    if send.conn is not None:
        try:
            send.conn.close()
        except socket.error:
            pass
        send.conn = None


@pytest.mark.enable_socket
def test_send_connection_closed(send_thread):
    """Test sending a VOEvent over loopback to a connection that
    is immediately closed."""
    sock = socket.socket(socket.AF_INET)
    sock.connect(('127.0.0.1', 53410))
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()


@pytest.mark.enable_socket
def test_send(send_thread):
    """Test sending a VOEvent over loopback."""
    # First, simulate connecting from a disallowed IP address.
    # The connection should be refused.
    app.conf['gcn_remote_address'] = '192.0.2.0'
    sock = socket.socket(socket.AF_INET)
    try:
        sock.settimeout(0.1)
        with pytest.raises(socket.error):
            sock.connect(('127.0.0.1', 53410))
            packet = _recv_packet(sock)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        sock.close()

    # Now, simulate connecting from the allowed IP address.
    # The VOEvent should be received.
    app.conf['gcn_remote_address'] = '127.0.0.1'
    sock = socket.socket(socket.AF_INET)
    try:
        sock.settimeout(0.1)
        sock.connect(('127.0.0.1', 53410))
        packet = _recv_packet(sock)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        sock.close()
    assert packet == voevent.encode('utf-8')


@pytest.mark.enable_socket
def test_listen(monkeypatch):
    """Test that the listen task would correctly launch gcn.listen()."""
    mock_gcn_listen = MagicMock()
    monkeypatch.setattr('gcn.listen', mock_gcn_listen)
    listen.run()
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
    handler.dispatch(*fake_gcn(10000))
    record, = caplog.records
    assert record.message == 'ignoring unrecognized key: 10000'


def test_unregistered_notice_type(caplog):
    """Test handling an unregistered notice type."""
    caplog.set_level(logging.WARNING)
    handler.dispatch(*fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
    record, = caplog.records
    assert record.message == ('ignoring unrecognized key: '
                              '<NoticeType.SWIFT_UVOT_POS_NACK: 89>')


@pytest.fixture
def reset_handlers():
    old_handler = dict(handler)
    handler.clear()
    yield
    handler.update(old_handler)


def test_registered_notice_type(reset_handlers):
    @handler(gcn.NoticeType.AGILE_POINTDIR, gcn.NoticeType.AGILE_TRANS)
    def agile_handler(payload):
        pass

    with patch.object(agile_handler, 'run') as mock_run:
        handler.dispatch(*fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
        mock_run.assert_not_called()
        handler.dispatch(*fake_gcn(gcn.NoticeType.AGILE_POINTDIR))
        mock_run.assert_called_once()
