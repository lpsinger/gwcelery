"""Subsystem for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import contextlib
import socket
import struct
import time

from celery.utils.log import get_task_logger
from celery_eternal import EternalTask, EternalProcessTask
from gcn import get_notice_type, NoticeType
import gcn

from ...celery import app
from ..core import DispatchHandler

log = get_task_logger(__name__)


@app.task(base=EternalTask, bind=True)
def broker(self):
    """Single-client VOEvent broker for sending notices to GCN.

    This is a single-client VOEvent broker (e.g. server). It listens for a
    connection from address :obj:`~gwcelery.celery.Base.gcn_bind_address` and
    port :obj:`~gwcelery.celery.Base.gcn_bind_port`.
    """
    with contextlib.closing(socket.socket(socket.AF_INET)) as sock:
        sock.settimeout(1.0)
        sock.bind((app.conf['gcn_bind_address'], app.conf['gcn_bind_port']))
        sock.listen(0)
        while not self.is_aborted():
            try:
                conn, (addr, _) = sock.accept()
            except socket.timeout:
                continue
            if addr == app.conf['gcn_remote_address']:
                log.info('accepted connection from remote host %s', addr)
                break
            else:
                log.error('denied connection from remote host %s', addr)
                conn.close()
        else:  # self.is_aborted()
            return

    with contextlib.closing(conn):
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', 1, 0))
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1)

        while not self.is_aborted():
            # Get next payload from queue in first-in, first-out fashion
            payload = self.backend.lindex(_queue_name, 0)
            if payload is None:
                time.sleep(1)
                continue
            nbytes = len(payload)

            log.info('sending payload of %d bytes', nbytes)
            conn.sendall(struct.pack('!I', nbytes) + payload)
            self.backend.lpop(_queue_name)


_queue_name = broker.name + '.voevent-queue'


@app.task(bind=True, ignore_result=True, shared=False)
def send(self, payload):
    """Send a VOEvent to GCN.

    Under the hood, this task just pushes the payload onto a Redis queue,
    and :func:`~gwcelery.tasks.gcn.broker` sends it."""
    self.backend.rpush(_queue_name, payload.encode('utf-8'))


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
"""Function decorator to register a handler callback for specified GCN notice
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
    gcn.listen(handler=handler.dispatch)
