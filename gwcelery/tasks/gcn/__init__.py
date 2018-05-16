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
import gcn

from ...celery import app

log = get_task_logger(__name__)

_size_struct = struct.Struct("!I")


class SendTask(Task):

    def __init__(self):
        self.conn = None


@app.task(queue='voevent', base=SendTask, ignore_result=True, bind=True,
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


_handlers = {}


def handler(notice_types, *args, **kwargs):
    """Function decorator to register a handler callback for specified GCN
    notice types. The decorated function is turned into a Celery task, which
    will be automatically called whenever a matching GCN notice is received.

    Parameters
    ----------
    notice_type : list
        List of GCN notice types to accept

    Other Parameters
    ----------------
    \*args
        Additional arguments for `celery.Celery.task`.
    \*\*kwargs
        Additional keyword arguments for `celery.Celery.task`.

    Examples
    --------
    Declare a new handler like this::

        @handler([gcn.NoticeType.FERMI_GBM_GND_POS,
                  gcn.NoticeType.FERMI_GBM_FIN_POS])
        def handle_fermi(payload):
            root = lxml.etree.fromstring(payload)
            # do work here...
    """

    def wrap(f):
        f = app.task(*args, **kwargs)(f)
        for notice_type in notice_types:
            _handlers.setdefault(notice_type, []).append(f)
        return f

    return wrap


def _handle(payload, root):
    notice_type = gcn.get_notice_type(root)

    try:
        handlers = _handlers[notice_type]
    except KeyError:
        try:
            # Try to cast the notice type to an enum value to make
            # the log message more informative.
            notice_type = gcn.NoticeType(notice_type)
        except ValueError:
            # If it's invalid, that's OK; we only want it to make log
            # messages prettier anyway and we can live with an int.
            pass
        log.warn('ignoring unrecognized GCN notice type: %r', notice_type)
    else:
        for h in handlers:
            h.s(payload).delay()


@app.task(base=EternalProcessTask, shared=False)
def listen():
    """Long-running GCN listener task."""
    gcn.listen(handler=_handle)
