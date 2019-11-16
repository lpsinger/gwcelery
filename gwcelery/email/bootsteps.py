from threading import Thread

from celery import bootsteps
from celery.utils.log import get_logger
from imapclient import IMAPClient
from safe_netrc import netrc

from .signals import email_received

__all__ = ('Receiver',)

log = get_logger(__name__)


class EmailBootStep(bootsteps.ConsumerStep):
    """Generic boot step to limit us to appropriate kinds of workers.

    Only include this bootstep in workers that are started with the
    ``--email`` command line option.
    """

    def __init__(self, consumer, email=False, **kwargs):
        self.enabled = bool(email)

    def start(self, consumer):
        log.info('Starting %s', self.name)

    def stop(self, consumer):
        log.info('Stopping %s', self.name)


class Receiver(EmailBootStep):
    """Run the global email receiver in background thread."""

    name = 'email client'

    def _runloop(self):
        username, _, password = netrc().authenticators(self._host)
        with IMAPClient(self._host, use_uid=True) as conn:
            conn.login(username, password)
            conn.select_folder('inbox')
            while self._running:
                messages = conn.search()
                for msgid, data in conn.fetch(messages, ['RFC822']).items():
                    email_received.send(None, rfc822=data[b'RFC822'])
                    conn.delete_messages(msgid)
                conn.idle()
                responses = []
                while self._running and not responses:
                    responses = conn.idle_check(timeout=5)
                conn.idle_done()

    def create(self, consumer):
        super().create(consumer)
        self._host = consumer.app.conf['email_host']
        self._running = True
        self._thread = Thread(target=self._runloop)

    def start(self, consumer):
        super().start(consumer)
        self._thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        self._running = False
        self._thread.join()
