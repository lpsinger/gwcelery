import socket
import struct

from celery import Task
from celery.utils.log import get_task_logger

from ..celery import app

# Logging
log = get_task_logger(__name__)

_size_struct = struct.Struct("!I")


class SendTask(Task):

    def __init__(self):
        self.conn = None


@app.task(queue='voevent', base=SendTask, ignore_result=True,
          autoretry_for=(socket.error,), default_retry_delay=0.001,
          retry_backoff=True, retry_kwargs=dict(max_retries=None))
def send(payload):
    """Task to send VOEvents. Supports only a single client."""
    payload = payload.encode('utf-8')
    nbytes = len(payload)

    conn = send.conn
    send.conn = None

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
    except:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except:
            log.exception('failed to shut down socket')
        conn.close()
        raise
    send.conn = conn
