"""LVAlert client."""
import json

from celery.utils.log import get_task_logger

from ..lvalert.signals import lvalert_received
from .. import app
from .core import DispatchHandler
from . import gracedb

log = get_task_logger(__name__)


class _LVAlertDispatchHandler(DispatchHandler):

    def __call__(self, *keys, **kwargs):
        try:
            lvalert_nodes = app.conf['lvalert_nodes']
        except KeyError:
            lvalert_nodes = app.conf['lvalert_nodes'] = set()
        lvalert_nodes.update(keys)
        return super().__call__(*keys, **kwargs)

    def process_args(self, node, payload):
        # Determine GraceDB service URL
        alert = json.loads(payload)
        try:
            try:
                self_link = alert['object']['links']['self']
            except KeyError:
                self_link = alert['object']['self']
        except KeyError:
            log.exception('LVAlert message does not contain an API URL: %r',
                          alert)
            return None, None, None
        base, api, _ = self_link.partition('/api/')
        service = base + api

        if service != gracedb.client.url:
            log.warning('ignoring LVAlert message because it is intended for '
                        'GraceDB server %s, but we are set up for server %s',
                        service, gracedb.client.url)
            return None, None, None

        return super().process_args(node, alert)


handler = _LVAlertDispatchHandler()
r"""Function decorator to register a handler callback for specified LVAlert
message types. The decorated function is turned into a Celery task, which will
be automatically called whenever a matching LVAlert message is received.

Parameters
----------
\*keys
    List of LVAlert message types to accept
\*\*kwargs
    Additional keyword arguments for :meth:`celery.Celery.task`.

Examples
--------
Declare a new handler like this::

    @lvalert.handler('cbc_gstlal',
                     'cbc_spiir',
                     'cbc_pycbc',
                     'cbc_mbtaonline')
    def handle_cbc(alert_content):
        # do work here...
"""


@lvalert_received.connect
def _on_lvalert_received(node, payload, **kwargs):
    handler.dispatch(node, payload)
