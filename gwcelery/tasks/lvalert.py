"""LVAlert client."""
import json
import time

from celery_eternal import EternalTask
from celery.utils.log import get_task_logger
import sleek_lvalert

from ..import app
from .core import DispatchHandler
from . import gracedb

log = get_task_logger(__name__)


class _LVAlertDispatchHandler(DispatchHandler):

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

        if service != gracedb.client._service_url:
            log.warning('ignoring LVAlert message because it is intended for '
                        'GraceDB server %s, but we are set up for server %s',
                        service, gracedb.client._service_url)
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


@app.task(base=EternalTask, bind=True, shared=False)
def listen(self):
    """Listen for LVAlert messages forever. LVAlert messages are dispatched
    asynchronously to tasks that have been registered with
    :meth:`gwcelery.tasks.lvalert.handler`."""

    log.info('Starting client')
    client = sleek_lvalert.LVAlertClient(server=app.conf['lvalert_host'])
    client.connect()
    client.process(block=False)

    log.info('Updating subscriptions')
    current_subscriptions = set(client.get_subscriptions())
    needed_subscriptions = set(handler.keys())
    client.subscribe(*(needed_subscriptions - current_subscriptions))

    log.info('Listening for pubsub messages')
    client.listen(handler.dispatch)

    while not self.is_aborted():
        time.sleep(1)
    log.info('Disconnecting')
    client.abort()
    log.info('Exiting')
