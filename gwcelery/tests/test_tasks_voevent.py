import json
import socket
from threading import Thread
from time import sleep

from gcn.voeventclient import _recv_packet

from ..tasks.voevent import send
from . import *

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


def test_send_connection_closed(send_thread):
    """Test sending a VOEvent over loopback to a connection that
    is immediately closed."""
    sock = socket.socket(socket.AF_INET)
    sock.connect(('127.0.0.1', 53410))
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()


def test_send(send_thread):
    """Test sending a VOEvent over loopback."""
    # First, simulate connecting from a disallowed IP address.
    # The connection should be refused.
    app.conf['gcn_remote_address'] = '192.0.2.0'
    sock = socket.socket(socket.AF_INET)
    try:
        sock.settimeout(0.1)
        with pytest.raises(OSError):
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
