"""Subsystem for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import socket
import subprocess

import billiard
from celery.utils.log import get_task_logger
from celery_eternal import EternalProcessTask
from comet.icomet import IHandler
from comet.utility import xml_document
from comet.protocol import VOEventSenderFactory
from gcn import get_notice_type, NoticeType
from twisted.application import app as twisted_app
from twisted.internet import reactor
from twisted.python.runtime import platformType
from zope.interface import implementer

from ...import app
from ..core import DispatchHandler

if platformType == 'win32':
    from twisted.scripts._twistw import ServerOptions, \
        WindowsApplicationRunner as ApplicationRunner
else:
    from twisted.scripts._twistd_unix import ServerOptions, \
        UnixApplicationRunner as ApplicationRunner

log = get_task_logger(__name__)


class _VOEventDispatchHandler(DispatchHandler):

    def process_args(self, event):
        notice_type = get_notice_type(event.element)

        # Just cast to enum for prettier log messages
        try:
            notice_type = NoticeType(notice_type)
        except ValueError:
            pass

        return notice_type, (event.raw_bytes,), {}


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


@implementer(IHandler)
class _VOEventHandler:
    """ Comet VOEvent handler."""
    name = 'GWCelery VOEvent dispatch handler'
    __call__ = handler.dispatch


def _get_ephemeral_port():
    """Get an ephemeral (unused, high numbered) port. Note that there is
    inherently a race condition in using this function because there is no
    guarantee that the port is still not in use when the caller attempts to use
    it."""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        _, port = s.getsockname()
    return port


@app.task(base=EternalProcessTask, bind=True, shared=False)
def broker(self):
    """Run an embedded :doc:`Comet VOEvent broker <comet:usage/broker>` to send
    and recieve GCNs."""
    # Look up the broker broadcast port from the global configuration object.
    _, _, broadcast_port = app.conf['gcn_broker_address'].partition(':')

    # Pick an ephemeral port to listen to for VOEvent submission.
    # Using an ephemeral port allows us to run multiple instances of
    # GWCelery on the same machine, which may be useful for testing.
    author_port = str(_get_ephemeral_port())
    self.backend.client.set(self.name + '.port', author_port)

    # Assemble the command line options for Twisted.
    cmd = ['--nodaemon', '--pidfile=', 'comet', '--verbose',
           '--local-ivo', 'ivo://ligo.org/gwcelery',
           '--remote', app.conf['gcn_client_address'],
           '--receive', '--receive-port', author_port,
           '--author-whitelist', '127.0.0.0/8',
           '--broadcast', '--broadcast-port', broadcast_port,
           '--broadcast-test-interval', '0',
           *(_ for name in app.conf['gcn_broker_accept_addresses']
             for _ in ('--subscriber-whitelist', socket.gethostbyname(name)))]

    # Run Twisted.
    log.info('twistd %s', ' '.join(cmd))
    config = ServerOptions()
    config.parseOptions(cmd)
    config.subOptions['handlers'].append(_VOEventHandler())
    runner = ApplicationRunner(config)
    runner.run()
    if runner._exitSignal is not None:
        twisted_app._exitWithSignal(runner._exitSignal)


class _OneShotSender(VOEventSenderFactory):
    # This class is adapted from the comet-sendvo script.
    # It allows us to do a single-shot VOEvent submission without
    # knowing the path where comet-sendvo is installed.

    def clientConnectionLost(self, connector, reason):  # noqa: N802
        reactor.stop()

    def clientConnectionFailed(self, connector, reason):  # noqa: N802
        log.warn("Connection failed")
        reactor.stop()


def _send(message, port):
    # This function is adapted from the comet-sendvo script.
    # It allows us to do a single-shot VOEvent submission without
    # knowing the path where comet-sendvo is installed.

    event = xml_document(message)
    factory = _OneShotSender(event)
    reactor.connectTCP('localhost', port, factory)
    reactor.run()
    if not factory.ack:
        raise ConnectionError('Comet did not accept the event')


@app.task(bind=True, ignore_result=True, shared=False)
def send(self, message):
    """Send a VOEvent to the local Comet instance for forwarding to GCN.

    Internally, this works similarly to the :doc:`comet-sendvo
    <comet:usage/publisher>` command line tool. However, it spawns a separate
    subprocess because it seems like it is impossible with Twisted to block on
    a single-shot action more than once in the same Python session because of
    how the global singleton reactor object works."""

    # Look up the ephemeral port number saved in Redis.
    port = int(broker.backend.client.get(broker.name + '.port'))

    # Start the process, and wait until it exits.
    process = billiard.Process(target=_send, args=(message, port), daemon=True)
    process.start()
    process.join()

    # If the process failed, then raise an exception. The exception will report
    # that the called process was comet-sendvo, but of course this is a
    # harmless little lie.
    if process.exitcode != 0:
        raise subprocess.CalledProcessError(
            process.exitcode, ['comet-sendvo', '--port', str(port)])
