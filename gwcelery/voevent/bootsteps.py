import threading

from celery import bootsteps
from celery.concurrency import solo
from comet.icomet import IHandler
from comet.protocol.broadcaster import VOEventBroadcasterFactory
from comet.utility import WhitelistingFactory
from twisted.application.internet import TCPClient, TCPServer
from twisted.internet import reactor
from zope.interface import implementer

from .util import get_host_port, get_local_ivo, get_network
from .logging import log
from .signals import voevent_received
from .subscriber import VOEventSubscriberFactory

__all__ = ('Broadcaster', 'Reactor', 'Receiver')


class VOEventBootStep(bootsteps.ConsumerStep):
    """Generic boot step to limit us to appropriate kinds of workers."""

    def include_if(self, consumer):
        """Only include this bootstep in workers that are configured to listen
        to the ``voevent`` queue."""
        return 'voevent' in consumer.app.amqp.queues

    def create(self, consumer):
        if not isinstance(consumer.pool, solo.TaskPool):
            raise RuntimeError(
                'The VOEvent broker only works with the "solo" task pool. '
                'Start the worker with "--queues=voevent --pool=solo".')

    def start(self, consumer):
        log.info('Starting %s', self.name)

    def stop(self, consumer):
        log.info('Stopping %s', self.name)


class Reactor(VOEventBootStep):
    """Run the global Twisted reactor in background thread.

    The Twisted reactor is a global run loop that drives all Twisted services
    and operations. This boot step starts the Twisted reactor in a background
    thread when the Celery consumer starts, and stops the thread when the
    Consumer terminates."""

    name = 'Twisted reactor'

    def __init__(self, consumer, **kwargs):
        self._thread = None

    def create(self, consumer):
        super().create(consumer)
        self._thread = threading.Thread(target=reactor.run, args=(False,))

    def start(self, consumer):
        super().start(consumer)
        self._thread.start()

    def stop(self, consumer):
        super().stop(consumer)
        reactor.callFromThread(reactor.stop)
        self._thread.join()


class TwistedService(VOEventBootStep):
    """A generic bootstep to create, start, and stop a Twisted service."""

    requires = VOEventBootStep.requires + (Reactor,)

    def __init__(self, consumer, **kwargs):
        self._service = None

    def create(self, consumer):
        super().create(consumer)
        self._service = self.create_service(consumer)

    def create_service(self, consumer):
        raise NotImplementedError

    def start(self, consumer):
        super().start(consumer)
        reactor.callFromThread(self._service.startService)

    def stop(self, consumer):
        super().stop(consumer)
        reactor.callFromThread(self._service.stopService)


class Broadcaster(TwistedService):
    """Comet-based VOEvent broadcaster.

    Run a Comet-based VOEvent broadcaster
    (:class:`comet.protocol.broadcaster.VOEventBroadcasterFactory`). Starts
    after the :class:`~gwcelery.voevent.bootsteps.Reactor` bootstep.

    A few :doc:`configuration options <configuration>` are available:

    * ``voevent_broadcaster_address``: The address to bind to, in
      :samp:`{host}:{port}` format.
    * ``voevent_broadcaster_whitelist``: A list of hostnames, IP addresses, or
       CIDR address ranges from which to accept connections.

    The list of active connections is made available :ref:`inspection
    <celery:worker-inspect>` with the ``gwcelery inspect stats`` command under
    the ``voevent-broker-peers`` key.
    """

    name = 'VOEvent broadcaster'

    def create_service(self, consumer):
        conf = consumer.app.conf
        local_ivo = get_local_ivo(consumer.app)
        host, port = get_host_port(conf['voevent_broadcaster_address'])
        allow = [get_network(a) for a in conf['voevent_broadcaster_whitelist']]
        conf['voevent_broadcaster_factory'] = self._factory = factory = \
            VOEventBroadcasterFactory(local_ivo, 0)
        if allow:
            factory = WhitelistingFactory(factory, allow, 'subscription')
        return TCPServer(port, factory, interface=host)

    def info(self, consumer):
        return {'voevent-broker-peers': [
            b.transport.getPeer().host for b in self._factory.broadcasters]}


@implementer(IHandler)
class Handler:
    """Comet VOEvent handler that forwards the event to a Celery signal."""

    def __call__(self, event):
        reactor.callInThread(
            voevent_received.send, sender=None, xml_document=event)


class Receiver(TwistedService):
    """VOEvent receiver.

    Run a Comet-based VOEvent receiver
    (:class:`comet.protocol.subscriber.VOEventSubscriberFactory`). Starts after
    the :class:`~gwcelery.voevent.bootsteps.Reactor` bootstep.

    A few :doc:`configuration options <configuration>` are available:

    * ``voevent_receiver_address``: The address to connect to, in
      :samp:`{host}:{port}` format.

    The list of active connections is made available :ref:`inspection
    <celery:worker-inspect>` with the ``gwcelery inspect stats`` command under
    the ``voevent-receiver-peers`` key.
    """

    name = 'VOEvent receiver'

    requires = TwistedService.requires + (
        'celery.worker.consumer.tasks:Tasks',)

    def create_service(self, consumer):
        conf = consumer.app.conf
        local_ivo = get_local_ivo(consumer.app)
        host, port = get_host_port(conf['voevent_receiver_address'])
        self._factory = factory = VOEventSubscriberFactory(
            local_ivo=local_ivo, handlers=[Handler()])
        return TCPClient(host, port, factory)

    def info(self, consumer):
        return {'voevent-receiver-peers': [
            b.transport.getPeer().host for b in self._factory.subscribers]}
