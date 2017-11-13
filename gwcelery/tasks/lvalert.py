import netrc
import os
import uuid

from celery.utils.log import get_task_logger
# pubsub import must come first because it overloads part of the
# StanzaProcessor class
import ligo.lvalert.pubsub
from pyxmpp.all import JID, TLSSettings
from pyxmpp.jabber.all import Client
from pyxmpp.interface import implements
from pyxmpp.interfaces import IMessageHandlersProvider

from ..celery import app
from ..util.eternal import EternalTask
from .dispatch import dispatch

# Logging
log = get_task_logger(__name__)


class LVAlertHandler(object):
    """Provides the actions taken when an event arrives."""
    implements(IMessageHandlersProvider)

    def get_message_handlers(self):
        return [(None, self.message)]

    def message(self, stanza):
        log.info('got message')
        e = self.get_entry(stanza)
        if e:
            log.info('dispatching')
            dispatch.s(e).delay()
        return True

    def get_entry(self, stanza):
        c = stanza.xmlnode.children
        while c:
            try:
                if c.name=="event":
                    return c.getContent()
            except libxml2.treeError:
                pass
            c = c.next
        return None


class LVAlertClient(Client):

    def __init__(self, task, server):
        self.__task = task
        resource = uuid.uuid4().hex
        netrcfile = os.environ.get('NETRC')
        auth = netrc.netrc(netrcfile).authenticators(server)
        if auth is None:
            raise RuntimeError('No matching netrc entry found')
        username, _, password = auth
        jid = JID(username + '@' + server + '/' + resource)
        log.info('lvalert_listen connecting: %r', jid)
        tls_settings = TLSSettings(require=True, verify_peer=False)
        Client.__init__(self, jid, password,
                        auth_methods=['sasl:GSSAPI', 'sasl:PLAIN'],
                        tls_settings=tls_settings, keepalive=30)
        self.interface_providers = [LVAlertHandler()]

    def idle(self):
        Client.idle(self)
        if self.__task.is_aborted():
            self.disconnect()


@app.task(base=EternalTask, bind=True, ignore_result=True)
def lvalert_listen(self):
    """LVAlert listener."""
    client = LVAlertClient(self, app.conf['lvalert_host'])
    client.connect()
    client.loop(1)
