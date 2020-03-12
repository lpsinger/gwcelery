import asyncio

from celery.utils.log import get_logger
import sleek_lvalert

log = get_logger(__name__)


class LVAlertClient(sleek_lvalert.LVAlertClient):

    def __init__(self, *args, nodes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._needed_subscriptions = set(nodes or ())
        self.add_event_handler('session_start', self._resubscribe)
        self.add_event_handler('session_start', self._refresh)
        self.add_event_handler('pubsub_subscription', self._refresh)
        self._current_subscriptions = set()

    async def _resubscribe(self, *args):
        log.info('Resubscribing to PubSub nodes')
        await self._refresh()
        to_subscribe = self._needed_subscriptions - self.subscriptions
        to_unsubscribe = self.subscriptions - self._needed_subscriptions
        await asyncio.gather(self.subscribe(*to_subscribe),
                             self.unsubscribe(to_unsubscribe))

    async def _refresh(self, *args):
        log.info('Subscriptions detected')
        self._current_subscriptions = set(await self.get_subscriptions())
        log.info('Current subscriptions: %r', self._current_subscriptions)

    @property
    def subscriptions(self):
        return self._current_subscriptions
