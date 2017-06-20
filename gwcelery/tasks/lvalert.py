import netrc
import uuid

from celery import signals
from celery_singleton import clear_locks, Singleton
from celery.utils.log import get_task_logger
# pubsub import must come first because it overloads part of the
# StanzaProcessor class
import ligo.lvalert.pubsub
from pyxmpp.all import JID, TLSSettings
from pyxmpp.jabber.all import Client
from pyxmpp.interface import implements
from pyxmpp.interfaces import IMessageHandlersProvider

from ..celery import app
from .dispatch import dispatch

# Logging
log = get_task_logger(__name__)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Schedule periodic tasks."""
    # Every second, make sure that lvalert_listen is running.
    sender.add_periodic_task(1.0, lvalert_listen.s('lvalert-test.cgca.uwm.edu'))


@signals.beat_init.connect
def setup_beat(sender, **kwargs):
    clear_locks(app)


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


@app.task(base=Singleton, ignore_result=True)
def lvalert_listen(server):
    """LVAlert listener."""
    resource = uuid.uuid4().hex
    username, _, password = netrc.netrc().authenticators(server)
    jid = JID(username + '@' + server + '/' + resource)
    log.info('lvalert_listen connecting: %r', jid)
    tls_settings = TLSSettings(require=True, verify_peer=False)
    client = Client(jid, password,
                    auth_methods=['sasl:GSSAPI', 'sasl:PLAIN'], keepalive=30,
                    tls_settings=tls_settings)
    client.interface_providers = [LVAlertHandler()]
    client.connect()
    try:
        client.loop(1)
    except KeyboardInterrupt:
        client.disconnect()
    else:
        raise RuntimeError('lvalert_listen exited early!')
