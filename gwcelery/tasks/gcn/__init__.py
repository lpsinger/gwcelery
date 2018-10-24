"""Subsystem for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import socket
import struct
import time

from celery.utils.log import get_task_logger
from celery_eternal import EternalTask, EternalProcessTask
from gcn.voeventclient import _get_now_iso8601, _recv_packet, _send_packet
from gcn import get_notice_type, NoticeType
import gcn

from ...import app
from ..core import DispatchHandler

log = get_task_logger(__name__)


IAMALIVE = '''<?xml version="1.0" encoding="UTF-8"?>
<trn:Transport role="iamalive" version="1.0"
xmlns:trn="http://telescope-networks.org/schema/Transport/v1.1"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://telescope-networks.org/schema/Transport/v1.1
http://telescope-networks.org/schema/Transport-v1.1.xsd">
<Origin>{}</Origin><TimeStamp>{}</TimeStamp>
</trn:Transport>'''


KEEPALIVE_TIME = 60  # Time in seconds between keepalives


def _host_port(address):
    host, port = address.split(':')
    return host, int(port)


@app.task(base=EternalTask, bind=True)
def broker(self):
    """Single-client VOEvent broker for sending notices to GCN.

    This is a basic VOEvent broker. It binds to the address
    :obj:`~gwcelery.conf.gcn_broker_address` and accepts
    one connection at a time from any host whose address is listed in
    :obj:`~gwcelery.conf.gcn_broker_accept_addresses`.
    """
    fqdn = socket.getfqdn()
    host, port = _host_port(app.conf['gcn_broker_address'])
    accept_hosts = [socket.gethostbyname(host) for host in
                    app.conf['gcn_broker_accept_addresses']]

    with socket.socket() as sock:
        sock.settimeout(1.0)
        sock.bind((host, port))
        log.info('bound to %s', app.conf['gcn_broker_address'])
        sock.listen(0)
        while not self.is_aborted():
            try:
                conn, (addr, _) = sock.accept()
            except socket.timeout:
                continue
            if addr in accept_hosts:
                log.info('accepted connection from remote host %s', addr)
                break
            else:
                log.error('denied connection from remote host %s', addr)
                conn.close()
        else:  # self.is_aborted()
            return

    with conn:
        conn.settimeout(1.0)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', 1, 0))
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1)

        last_sent = time.monotonic()

        while not self.is_aborted():
            # Get next payload from queue in first-in, first-out fashion
            payload = self.backend.client.lindex(_queue_name, 0)
            if payload is not None:
                log.info('sending payload of %d bytes', len(payload))
                _send_packet(conn, payload)
                last_sent = time.monotonic()
                self.backend.client.lpop(_queue_name)
            elif time.monotonic() - last_sent > KEEPALIVE_TIME:
                timestamp = _get_now_iso8601()
                payload = IAMALIVE.format(fqdn, timestamp).encode('utf-8')
                log.info('sending keepalive')
                _send_packet(conn, payload)
                last_sent = time.monotonic()
            else:
                # Read (but ignore) any inbound packet
                try:
                    _recv_packet(conn)
                except socket.timeout:
                    pass


_queue_name = broker.name + '.voevent-queue'


@app.task(bind=True, ignore_result=True, shared=False)
def send(self, payload):
    """Send a VOEvent to GCN.

    Under the hood, this task just pushes the payload onto a Redis queue,
    and :func:`~gwcelery.tasks.gcn.broker` sends it."""
    self.backend.client.rpush(_queue_name, payload)


class _VOEventDispatchHandler(DispatchHandler):

    def process_args(self, payload, root):
        notice_type = get_notice_type(root)

        # Just cast to enum for prettier log messages
        try:
            notice_type = NoticeType(notice_type)
        except ValueError:
            pass

        return notice_type, (payload,), {}


handler = _VOEventDispatchHandler()
r"""Function decorator to register a handler callback for specified GCN notice
types. The decorated function is turned into a Celery task, which will be
automatically called whenever a matching GCN notice is received.

Parameters
----------
\*keys
    List of GCN notice types to accept
\*\*kwargs
    Additional keyword arguments for :meth:`celery.Celery.task`.

Examples
--------
Declare a new handler like this::

    @gcn.handler(gcn.NoticeType.FERMI_GBM_GND_POS,
                 gcn.NoticeType.FERMI_GBM_FIN_POS)
    def handle_fermi(payload):
        root = lxml.etree.fromstring(payload)
        # do work here...
"""


@app.task(base=EternalProcessTask, shared=False)
def listen():
    """Listen to GCN notices forever. GCN notices are dispatched asynchronously
    to tasks that have been registered with
    :meth:`gwcelery.tasks.gcn.handler`."""
    host, port = _host_port(app.conf['gcn_client_address'])
    gcn.listen(host, port, handler=handler.dispatch)
