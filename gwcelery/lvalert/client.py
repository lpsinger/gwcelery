import sleek_lvalert


class LVAlertClient(sleek_lvalert.LVAlertClient):

    def __init__(self, *args, nodes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._needed_subscriptions = set(nodes or ())
        self.add_event_handler('session_start', self._resubscribe)

    def _resubscribe(self, event):
        current_subscriptions = set(self.get_subscriptions())
        self.subscribe(*(self._needed_subscriptions - current_subscriptions))
