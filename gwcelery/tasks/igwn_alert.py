"""IGWN alert client."""
import json

from celery.utils.log import get_task_logger

from ..igwn_alert.signals import igwn_alert_received
from .. import app
from .core import DispatchHandler
from . import gracedb

log = get_task_logger(__name__)


class _IGWNAlertDispatchHandler(DispatchHandler):
    def __call__(self, *keys, **kwargs):
        try:
            igwn_alert_topics = app.conf['igwn_alert_topics']
        except KeyError:
            igwn_alert_topics = app.conf['igwn_alert_topics'] = set()
        igwn_alert_topics.update(keys)
        return super().__call__(*keys, **kwargs)

    def process_args(self, topic, alert):
        alert = json.loads(alert)
        # Determine GraceDB service URL
        try:
            try:
                self_link = alert['object']['links']['self']
            except KeyError:
                self_link = alert['object']['self']
        except KeyError:
            log.exception(
                'IGWN alert message does not contain an API URL: %r',
                alert)
            return None, None, None
        base, api, _ = self_link.partition('/api/')
        service = base + api

        if service != gracedb.client.url:
            # FIXME: this is probably redundant since IGWN alert client
            # is initialized using group gracedb-playground, gracedb-test etc.
            log.warning(
                'ignoring IGWN alert message because it is intended for '
                'GraceDB server %s, but we are set up for server %s',
                service, gracedb.client.url)
            return None, None, None

        return super().process_args(topic, alert)


handler = _IGWNAlertDispatchHandler()
r"""Function decorator to register a handler callback for specified IGWN alert
message types. The decorated function is turned into a Celery task, which will
be automatically called whenever a matching IGWN alert message is received.

Parameters
----------
\*keys
    List of IGWN alert message types to accept
\*\*kwargs
    Additional keyword arguments for :meth:`celery.Celery.task`.

Examples
--------
Declare a new handler like this::

    @igwn_alert.handler('cbc_gstlal',
                        'cbc_spiir',
                        'cbc_pycbc',
                        'cbc_mbta')
    def handle_cbc(alert_content):
        # do work here...
"""


@igwn_alert_received.connect
def _on_igwn_received(topic, payload, **kwargs):
    handler.dispatch(topic, payload)
