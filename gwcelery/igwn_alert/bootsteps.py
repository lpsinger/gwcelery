from threading import Thread

from celery import bootsteps
from celery.utils.log import get_logger
from igwn_alert import client

from .signals import igwn_alert_received

__all__ = ('Receiver',)

log = get_logger(__name__)


class IGWNAlertBootStep(bootsteps.ConsumerStep):
    """Generic boot step to limit us to appropriate kinds of workers.

    Only include this bootstep in workers that are started with the
    ``--igwn-alerts`` command line option.
    """

    def __init__(self, consumer, igwn_alert=False, **kwargs):
        self.enabled = bool(igwn_alert)

    def start(self, consumer):
        log.info('Starting %s', self.name)

    def stop(self, consumer):
        log.info('Stopping %s', self.name)


def _send_igwn_alert(topic, payload):
    """Shim to send Celery signal."""
    igwn_alert_received.send(None, topic=topic, payload=payload)


class Receiver(IGWNAlertBootStep):
    """Run the global IGWN alert receiver in background thread."""

    name = 'IGWN Alert client'

    def start(self, consumer):
        super().start(consumer)

        self._client = client(group=consumer.app.conf['igwn_alert_group'])
        self.thread = Thread(
            target=self._client.listen,
            args=(_send_igwn_alert, consumer.app.conf['igwn_alert_topics']),
            name='IGWNReceiverThread')
        self.thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        self.thread.join()
        self._client.disconnect()

    def info(self, consumer):
        return {'igwn-alert-topics': consumer.app.conf[
            'igwn_alert_topics'].intersection(self._client.get_topics())}
