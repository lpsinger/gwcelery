from celery import bootsteps
from celery.utils.log import get_logger

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

    def start(self, consumer):
        super().start(consumer)
        from .client import LVAlertClient
        self._client = LVAlertClient(
            server=consumer.app.conf['lvalert_host'],
            nodes=consumer.app.conf['lvalert_nodes'])
        self._client.connect()
        self._client.process()
        self._client.listen(_send_lvalert_received)

    def stop(self, consumer):
        super().stop(consumer)
        self._client.disconnect()

    def info(self, consumer):
        try:
            lvalert_nodes = self._client.get_subscriptions()
        except:  # noqa: E722
            log.exception('failed to get info for lvalert-nodes')
            lvalert_nodes = []
        return {'lvalert-nodes': lvalert_nodes}
