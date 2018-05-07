"""Basic single-endpoint VOEvent broker."""
import socket
import struct
from urllib.parse import urlparse, urlunparse

from celery import Task
from celery.utils.log import get_task_logger
from celery_eternal import EternalProcessTask
import gcn
import lxml.etree

from ..celery import app
from ..tasks import gracedb

# Logging
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
    """Task to send VOEvents. Supports only a single client."""
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


@app.task(ignore_result=True, shared=False)
def validate(payload):
    """Check that the contents of a public LIGO/Virgo GCN matches the original
    VOEvent in GraceDB."""
    root = lxml.etree.fromstring(payload)

    # Which GraceDB ID does this refer to?
    graceid = root.find("./What/Param[@name='GraceID']").attrib['value']

    # Which VOEvent does this refer to?
    u = urlparse(root.attrib['ivorn'])
    assert u.scheme == 'ivo', (
        'IVORN has unexpected scheme: {!r}'.format(u.scheme))
    assert u.netloc == 'nasa.gsfc.gcn', (
        'IVORN has unexpected netloc: {!r}'.format(u.netloc))
    assert u.path == '/LVC', (
        'IVORN has unexpected path: {!r}'.format(u.path))
    local_id = u.fragment
    filename = local_id + '.xml'

    # Which GraceDB server does this refer to?
    u = urlparse(root.find("./What/Param[@name='EventPage']").attrib['value'])
    service = urlunparse((u.scheme, u.netloc, '/api/', None, None, None))

    # Download and parse original VOEvent
    orig = lxml.etree.fromstring(gracedb.download(filename, graceid, service))

    xpath = ".//Param[@name='{}']"
    for orig_name, root_name in [
            ['skymap_fits_shib', 'SKYMAP_URL_FITS_SHIB'],
            ['skymap_fits_x509', 'SKYMAP_URL_FITS_X509'],
            ['skymap_fits_basic', 'SKYMAP_URL_FITS_BASIC'],
            ['skymap_png_shib', 'SKYMAP_URL_PNG_SHIB'],
            ['skymap_png_x509', 'SKYMAP_URL_PNG_X509'],
            ['skymap_png_basic', 'SKYMAP_URL_PNG_BASIC']]:

        orig_elem = orig.find(xpath.format(orig_name))
        root_elem = root.find(xpath.format(root_name))

        if orig_elem is None:
            assert root_elem is None, (
                'GCN has unexpected parameter: {!r}'.format(root_name))
        else:
            assert root_elem is not None, (
                'GCN is missing parameter: {!r}'.format(root_name))
            orig_value = orig_elem.attrib.get('value')
            root_value = root_elem.attrib.get('value')
            assert root_value == orig_value, (
                'GCN parameter {!r} has value {!r}, but '
                'original VOEvent parameter {!r} '
                'has value {!r}'.format(
                    root_name, root_value, orig_name, orig_value))

    # Find matching GraceDB log entry
    log = gracedb.get_log(graceid, service)
    entry, = (e for e in log if e['filename'] == filename)
    log_number = entry['N']

    # Tag the VOEvent to indicate that it was received correctly
    gracedb.create_tag('gcn_received', log_number, graceid, service)


@gcn.include_notice_types(
    gcn.notice_types.LVC_PRELIMINARY,
    gcn.notice_types.LVC_INITIAL,
    gcn.notice_types.LVC_UPDATE
)
def handle(payload, root):
    validate.delay(payload)


@app.task(base=EternalProcessTask, shared=False)
def listen():
    """Listen for public GCNs and validate the contents of public LIGO/Virgo
    GCNs by passing their contents to :obj:`validate`."""
    gcn.listen(handler=handle)
