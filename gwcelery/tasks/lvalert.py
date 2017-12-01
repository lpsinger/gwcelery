import netrc
import os
import uuid

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
from ..util.eternal import EternalTask
from .dispatch import dispatch

# Logging
log = get_task_logger(__name__)

ns = {'ns1': 'http://jabber.org/protocol/pubsub#event',
      'ns2': 'http://jabber.org/protocol/pubsub'}


def filter_messages(xml):
    for node in xml.iterfind('.//ns1:items[@node]', ns):
        print('***', node.attrib['node'])
        if node.attrib['node'] in app.conf['lvalert_node_whitelist']:
            for entry in node.iterfind('.//ns2:entry', ns):
                yield entry.text


class LVAlertClient(EventHandler, TimeoutHandler, XMPPFeatureHandler):

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
        for text in filter_messages(stanza.as_xml()):
            log.debug('Dispatching: %s', text)
            dispatch.s(text).delay()
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


@app.task(base=EternalTask, bind=True, ignore_result=True, shared=False)
def lvalert_listen(self):
    """LVAlert listener."""
    LVAlertClient(app.conf['lvalert_host'], self).run()
