import asyncio
from threading import Thread

from celery import bootsteps
from celery.utils.log import get_logger

from . import client
from .signals import lvalert_received

__all__ = ('Receiver',)

log = get_logger(__name__)


class LVAlertBootStep(bootsteps.ConsumerStep):
    """Generic boot step to limit us to appropriate kinds of workers.

    Only include this bootstep in workers that are started with the
    ``--lvalert`` command line option.
    """

    def __init__(self, consumer, lvalert=False, **kwargs):
        self.enabled = bool(lvalert)

    def start(self, consumer):
        log.info('Starting %s', self.name)

    def stop(self, consumer):
        log.info('Stopping %s', self.name)


def _send_lvalert_received(node, payload):
    """Shim to send Celery signal."""
    lvalert_received.send(None, node=node, payload=payload)


class Receiver(LVAlertBootStep):
    """Run the global LVAlert receiver in background thread."""

    name = 'LVAlert client'

    def create(self, consumer):
        super().create(consumer)
        self._client = client.LVAlertClient(
            server=consumer.app.conf['lvalert_host'],
            nodes=consumer.app.conf['lvalert_nodes'])
        self._client.listen(_send_lvalert_received)
        self._thread = Thread(target=self._run)

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._client.disconnected = loop.create_future()
        self._client.loop = loop
        self._client.start()

    def start(self, consumer):
        super().start(consumer)
        self._thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        self._client.stop()
        self._thread.join()

    def info(self, consumer):
        return {'lvalert-nodes': list(self._client.subscriptions)}
