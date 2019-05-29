from celery.utils.log import get_logger
import sleek_lvalert

log = get_logger(__name__)


class LVAlertClient(sleek_lvalert.LVAlertClient):

    def __init__(self, *args, nodes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._needed_subscriptions = set(nodes or ())
        self.add_event_handler('session_start', self._resubscribe)

    def _resubscribe(self, event):
        log.info('Resubscribing to PubSub nodes')
        current_subscriptions = set(self.get_subscriptions())
        self.subscribe(*(self._needed_subscriptions - current_subscriptions))
