"""LVAlert client."""
import json
import netrc
import os
import uuid

from celery_eternal import EternalTask
from celery.utils.log import get_task_logger
from pyxmpp2.client import Client
from pyxmpp2.interfaces import (EventHandler, event_handler,
                                message_stanza_handler, QUIT,
                                XMPPFeatureHandler)
from pyxmpp2.jid import JID
from pyxmpp2.mainloop.interfaces import TimeoutHandler, timeout_handler
from pyxmpp2.settings import XMPPSettings
from pyxmpp2.streamevents import DisconnectedEvent

from ..celery import app
from .core import DispatchHandler
from . import gracedb

log = get_task_logger(__name__)

ns = {'ns1': 'http://jabber.org/protocol/pubsub#event',
      'ns2': 'http://jabber.org/protocol/pubsub'}


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

        if service != gracedb.client.service_url:
            log.warn('ignoring LVAlert message because it is intended for '
                     'GraceDb server %s, but we are set up for server %s',
                     service, gracedb.client.service_url)
            return None, None, None

        return super().process_args(node, payload)


handler = _LVAlertDispatchHandler()
"""Function decorator to register a handler callback for specified LVAlert
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
                     'cbc_pycbc',
                     'cbc_mbta')
    def handle_cbc(alert_content):
        # do work here...
"""


def _handle_messages(xml):
    for node in xml.iterfind('.//ns1:items[@node]', ns):
        for entry in node.iterfind('.//ns2:entry', ns):
            handler.dispatch(node.attrib['node'], entry.text)


class _LVAlertClient(EventHandler, TimeoutHandler, XMPPFeatureHandler):

    def __init__(self, server, task=None):
        # Look up username and password from the netrc file.
        netrcfile = os.environ.get('NETRC')
        auth = netrc.netrc(netrcfile).authenticators(server)
        if auth is None:
            raise RuntimeError('No matching netrc entry found')
        username, _, password = auth

        # Create a JID with a unique resource name.
        resource = uuid.uuid4().hex
        jid = JID(username + '@' + server + '/' + resource)

        settings = XMPPSettings(dict(
            starttls=True, tls_verify_peer=False, password=password))

        self.__task = task
        self.__client = Client(jid, [self], settings)
        self.__client.main_loop.add_handler(self)

    @event_handler(DisconnectedEvent)
    def __handle_disconnected(self, *args, **kwargs):
        return QUIT

    @message_stanza_handler()
    def __handle_message(self, stanza):
        log.info('Got message')
        _handle_messages(stanza.as_xml())
        return True

    @timeout_handler(1, recurring=True)
    def __handle_timeout(self, *args, **kargs):
        if self.__task is not None and self.__task.is_aborted():
            log.info('Task aborted, quitting event loop')
            self.__client.disconnect()
        return True

    def run(self):
        log.info('Connecting to %r', str(self.__client.jid))
        self.__client.connect()
        self.__client.run()
        log.info('Reached end of main loop')


@app.task(base=EternalTask, bind=True, shared=False)
def listen(self):
    """Listen for LVAlert messages forever. LVAlert messages are dispatched
    asynchronously to tasks that have been registered with
    :meth:`gwcelery.tasks.lvalert.handler`."""
    _LVAlertClient(app.conf['lvalert_host'], self).run()
