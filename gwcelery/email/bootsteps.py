from threading import Thread

from celery import bootsteps
from celery.utils.log import get_logger
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
        from imapclient import IMAPClient
        from imapclient.exceptions import IMAPClientAbortError

        username, _, password = netrc().authenticators(self._host)
        while self._running:
            try:
                log.info('Starting new connection')
                with IMAPClient(self._host, use_uid=True, timeout=30) as conn:
                    log.info('Logging in')
                    conn.login(username, password)
                    log.info('Selecting inbox')
                    conn.select_folder('inbox')
                    while self._running:
                        log.info('Searching for new messages')
                        messages = conn.search()
                        log.info('Fetching new messages')
                        for msgid, data in conn.fetch(
                                messages, ['RFC822']).items():
                            log.info('Sending signal for new email')
                            email_received.send(None, rfc822=data[b'RFC822'])
                            log.info('Deleting email')
                            conn.delete_messages(msgid)
                        log.info('Starting idle')
                        conn.idle()
                        responses = []
                        while self._running and not responses:
                            log.info('Checking idle')
                            responses = conn.idle_check(timeout=5)
                        log.info('Idle done')
                        conn.idle_done()
            except IMAPClientAbortError:
                log.exception('IMAP connection aborted')

    def create(self, consumer):
        super().create(consumer)
        self._host = consumer.app.conf['email_host']
        self._running = True
        self._thread = Thread(target=self._runloop, name='EmailClientThread')

    def start(self, consumer):
        super().start(consumer)
        self._thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        self._running = False
        self._thread.join()
