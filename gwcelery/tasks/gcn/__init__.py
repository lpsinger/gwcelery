"""Subsystem for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import socket
import subprocess
import tempfile

from celery.utils.log import get_task_logger
from celery_eternal import EternalTask, EternalProcessTask
from gcn import get_notice_type, NoticeType
import gcn

from ...import app
from ..core import DispatchHandler

log = get_task_logger(__name__)


def _get_ephemeral_port():
    """Get an ephemeral (unused, high numbered) port. Note that there is
    inherently a race condition in using this function because there is no
    guarantee that the port is still not in use when the caller attempts to use
    it."""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        _, port = s.getsockname()
    return port


@app.task(base=EternalTask, bind=True, shared=False)
def broker(self):
    """Run an embedded :doc:`Comet VOEvent broker <comet:usage/broker>` to send
    GCNs."""
    # Look up the broker broadcast port from the global configuration object.
    _, _, broadcast_port = app.conf['gcn_broker_address'].partition(':')

    # Pick an ephemeral port to listen to for VOEvent submission.
    # Using an ephemeral port allows us to run multiple instances of
    # GWCelery on the same machine, which may be useful for testing.
    author_port = str(_get_ephemeral_port())
    self.backend.client.set(self.name + '.port', author_port)

    # Create temporary directory for Comet's event database in order to ensure
    # isolation from any other instance of GWCelery on the same machine.
    with tempfile.TemporaryDirectory() as tmpdir:
        # Assemble the command line options for Twisted.
        subprocess.check_call([
            'twistd', '--nodaemon', '--pidfile=',
            'comet', '--verbose',
            '--local-ivo', 'ivo://ligo.org/gwcelery',
            '--receive',
            '--receive-port', author_port,
            '--author-whitelist', '127.0.0.0/8',
            '--broadcast',
            '--broadcast-port', broadcast_port,
            '--broadcast-test-interval', '0',
            '--eventdb', tmpdir,
            *(_ for name in app.conf['gcn_broker_accept_addresses'] for _ in
                ('--subscriber-whitelist', socket.gethostbyname(name)))
        ])


@app.task(ignore_result=True, shared=False)
def send(message):
    """Send a VOEvent to the local Comet instance for forwarding to GCN.

    Internally, this just calls :doc:`comet-sendvo <comet:usage/publisher>`."""

    # Look up the ephemeral port number saved in Redis.
    port = broker.backend.client.get(broker.name + '.port')

    # Send the VOEvent using comet-sendvo.
    subprocess.run(['comet-sendvo', '--port', port],
                   check=True, input=message, stderr=subprocess.PIPE)


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


def _host_port(address):
    host, port = address.split(':')
    return host, int(port)


@app.task(base=EternalProcessTask, shared=False)
def listen():
    """Listen to GCN notices forever. GCN notices are dispatched asynchronously
    to tasks that have been registered with
    :meth:`gwcelery.tasks.gcn.handler`."""
    host, port = _host_port(app.conf['gcn_client_address'])
    gcn.listen(host, port, handler=handler.dispatch)
