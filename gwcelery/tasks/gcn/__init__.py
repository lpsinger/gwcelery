"""Subsystem for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import socket
import struct

from celery import Task
from celery.utils.log import get_task_logger
from celery_eternal import EternalProcessTask
from gcn import get_notice_type, NoticeType
import gcn

from ...celery import app
from ..core import DispatchHandler

log = get_task_logger(__name__)

_size_struct = struct.Struct("!I")


class _SendTask(Task):

    def __init__(self):
        self.conn = None


@app.task(queue='voevent', base=_SendTask, ignore_result=True, bind=True,
          autoretry_for=(socket.error,), default_retry_delay=0.001,
          retry_backoff=True, retry_kwargs=dict(max_retries=None),
          shared=False)
def send(self, payload):
    """Send a VOEvent to GCN."""
    payload = payload.encode('utf-8')
    nbytes = len(payload)

    conn = self.conn
    self.conn = None

    if conn is None:
        log.info('creating new socket')
        sock = socket.socket(socket.AF_INET)
        try:
            sock.bind((app.conf['gcn_bind_address'],
                       app.conf['gcn_bind_port']))
            sock.listen(0)
            while True:
                conn, (addr, _) = sock.accept()
                if addr == app.conf['gcn_remote_address']:
                    break
                else:
                    log.error('connection denied to remote host %s', addr)
        finally:
            sock.close()
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                        struct.pack('ii', 1, 0))
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1)

    log.info('sending payload of %d bytes', nbytes)
    try:
        conn.sendall(_size_struct.pack(nbytes) + payload)
    except:  # noqa
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except:  # noqa
            log.exception('failed to shut down socket')
        conn.close()
        raise
    self.conn = conn


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
