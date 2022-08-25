import json
from threading import Thread
import warnings

from celery import bootsteps
from celery.utils.log import get_logger
from hop.models import JSONBlob
from hop.io import StartPosition
from igwn_alert import client

from .signals import igwn_alert_received

__all__ = ('Receiver',)

log = get_logger(__name__)


# FIXME: Remove once igwn_alert listener has a sentinel variable to
# indicate a shutdown from the main thread
# Relevant MR in igwn-alert client: https://git.ligo.org/computing/igwn-alert/client/-/merge_requests/12  # noqa: E501
class IGWNAlertClient(client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = 1
        self.until_eos = False  # FIXME: Revert to True when fix for autocommit is found  # noqa: E501
        self.running = False
        self.start_at = StartPosition.LATEST

    # mostly implemented from https://git.ligo.org/computing/igwn-alert/client/-/blob/main/igwn_alert/client.py  # noqa: E501
    def listen(self, callback=None, topic=None):
        """
        Set a callback to be executed for each pubsub item received.

        Parameters
        ----------
        callback : callable (optional)
            A function of two arguments: the topic and the alert payload.
            When set to :obj:`None`, print out alert payload.
        topic : :obj:`str`, or :obj:`list` of :obj:`str` (optional)
            Topic or list of topics to listen to. When set to :obj:`None`,
            then listen to all topics connected to user's credential.
        """
        self.running = True
        if topic:
            if isinstance(topic, str):
                topic = [topic]
            listen_topics = topic
        else:
            listen_topics = self.get_topics()
        s = self.open(self._construct_topic_url(listen_topics), "r")
        log.info("Opened connection to scimma")
        while self.running:
            try:
                for payload, metadata in s.read(
                        metadata=True,
                        batch_size=self.batch_size,
                        batch_timeout=self.batch_timeout):
                    # Fix in case message is in new format:
                    if isinstance(payload, JSONBlob):
                        payload = payload.content
                    else:
                        try:
                            payload = json.loads(payload)
                        except (json.JSONDecodeError, TypeError) as e:
                            warnings.warn("Payload is not valid "
                                          "json: {}".format(e))
                    if not callback:
                        print("New message from topic {topic}: {msg}"
                              .format(topic=metadata.topic, msg=payload))
                    else:
                        callback(topic=metadata.topic.split('.')[1],
                                 payload=payload)
            except (KeyboardInterrupt, SystemExit):
                self.running = False
        s.close()


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

        self._client = IGWNAlertClient(
            group=consumer.app.conf['igwn_alert_group'])
        self.thread = Thread(
            target=self._client.listen,
            args=(_send_igwn_alert, consumer.app.conf['igwn_alert_topics']),
            name='IGWNReceiverThread')
        self.thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        self._client.running = False
        self.thread.join()

    def info(self, consumer):
        return {'igwn-alert-topics': consumer.app.conf[
            'igwn_alert_topics'].intersection(self._client.get_topics())}
