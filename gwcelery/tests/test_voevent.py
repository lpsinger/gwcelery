import json
import socket
import threading
import time

from gcn.voeventclient import _recv_packet

from ..tasks.voevent import send
from . import *


def test_send():
    """Test sending a VOEvent over loopback"""
    # Test data
    with pkg_resources.resource_stream(
            __name__, 'data/lvalert_voevent.json') as f:
        lvalert = json.load(f)
    voevent = lvalert['object']['text']

    send_thread = threading.Thread(target=send, args=(voevent,))
    send_thread.daemon = True
    send_thread.start()
    time.sleep(0.1)
    try:
        # First, simulate connecting from a disallowed IP address.
        # The connection should be refused.
        app.conf['gcn_remote_address'] = '192.0.2.0'
        sock = socket.socket(socket.AF_INET)
        try:
            sock.settimeout(0.1)
            sock.connect(('127.0.0.1', 53410))
            with pytest.raises(socket.error):
                packet = _recv_packet(sock)
        finally:
            sock.shutdown(socket.SHUT_RDWR)
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
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        assert packet == voevent.encode('utf-8')
    finally:
        send_thread.join()

    # Lastly, simulate opening and immediately closing the socket.
    send.conn.close()
    send.conn = None
    send_thread = threading.Thread(target=send, args=(voevent,))
    send_thread.daemon = True
    send_thread.start()
    time.sleep(0.1)
    try:
        sock = socket.socket(socket.AF_INET)
        try:
            sock.connect(('127.0.0.1', 53410))
        finally:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
    finally:
        send_thread.join()
