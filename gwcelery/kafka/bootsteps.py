from hop import stream

from celery import bootsteps
from celery.concurrency import solo
from celery.utils.log import get_logger


__all__ = ('Producer',)

log = get_logger(__name__)


class KafkaBootStep(bootsteps.ConsumerStep):
    """Generic boot step to limit us to appropriate kinds of workers.

    Only include this bootstep in workers that are started with the
    ``--kafka`` command line option.
    """

    def include_if(self, consumer):
        """Only include this bootstep in workers that are configured to listen
        to the ``kafka`` queue.
        """
        return 'kafka' in consumer.app.amqp.queues

    def create(self, consumer):
        if not isinstance(consumer.pool, solo.TaskPool):
            raise RuntimeError(
                'The Kafka broker only works with the "solo" task pool. '
                'Start the worker with "--queues=kafka --pool=solo".')

    def start(self, consumer):
        log.info(f'Starting {self.name}, topics: ' + ' '.join[self.kafka_urls])

    def stop(self, consumer):
        log.info('Closing connection to topics: ' + ' '.join(self.kafka_urls))


class Producer(KafkaBootStep):
    """Run the global Kafka producer in a background thread."""

    name = 'Kafka producer'

    def start(self, consumer):
        super().start(consumer)
        consumer.app.conf['kafka_streams'] = {
            k: stream.open(v, 'w') for k, v in consumer.app.conf['kafka_urls']
        }

    def stop(self, consumer):
        super().stop(consumer)
        for s in consumer.app.conf['kafka_streams'].values():
            s.close()
