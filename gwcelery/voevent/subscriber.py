"""Subclasses of :class:`comet.protocol.VOEventSubscriber` and
:class:`comet.protocol.VOEventSubscriberFactory` that allow inspection of the
list of active subscribers.
"""
from comet.protocol.subscriber import (
    VOEventSubscriber as _VOEventSubscriber,
    VOEventSubscriberFactory as _VOEventSubscriberFactory)


class VOEventSubscriber(_VOEventSubscriber):

    def connectionMade(self, *args):  # noqa: N802
        self.factory.subscribers.append(self)
        super().connectionMade(*args)

    def connectionLost(self, *args):  # noqa: N802
        self.factory.subscribers.remove(self)
        return super().connectionLost(*args)


class VOEventSubscriberFactory(_VOEventSubscriberFactory):

    protocol = VOEventSubscriber

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscribers = []
