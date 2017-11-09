import socket
import struct

from celery import Task
from celery.utils.log import get_task_logger

from ..celery import app

# Logging
log = get_task_logger(__name__)

HOST = ''
PORT = 5341
REMOTE = '128.183.96.236' # capella2.gsfc.nasa.gov
_size_struct = struct.Struct("!I")


class SendTask(Task):

    def __init__(self):
        self.conn = None


@app.task(queue='voevent', base=SendTask, ignore_result=True, default_retry_delay=0.001, retry_backoff=True,
          autoretry_for=(socket.error,), retry_kwargs=dict(max_retries=None))
def send(payload):
    """Task to send VOEvents. Supports only a single client."""
    try:
        if send.conn is None:
            log.info('creating new socket')
            sock = socket.socket(socket.AF_INET)
            try:
                log.info('binding to %s:%d', HOST, PORT)
                sock.bind((HOST, PORT))
                log.info('listening for inbound connections')
                sock.listen(0)
                log.info('accepting connection')
                conn, (addr, port) = sock.accept()
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                    struct.pack('ii', 1, 0))
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1)
            finally:
                sock.close()
            if addr != REMOTE:
                raise socket.error(
                    'Connection denied to remote host {}'.format(addr))
            send.conn = conn

        nbytes = len(payload)
        log.info('sending payload of %d bytes', nbytes)
        send.conn.sendall(_size_struct.pack(nbytes) + payload)
    except:
        if send.conn is not None:
            try:
                try:
                    send.conn.shutdown(socket.SHUT_RDWR)
                finally:
                    send.conn.close()
            finally:
                send.conn = None
        raise
