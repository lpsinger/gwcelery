"""A Nagios plugin for monitoring GWCelery.

See https://nagios-plugins.org/doc/guidelines.html.
"""
from enum import IntEnum
from sys import exit
from traceback import format_exc, format_exception

import click
import kombu.exceptions

# Make sure that all tasks are registered
from .. import tasks  # noqa: F401


class NagiosPluginStatus(IntEnum):
    """Nagios plugin status codes."""

    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


class NagiosCriticalError(Exception):
    """An exception that maps to a Nagios status of `CRITICAL`."""


def get_active_queues(inspector):
    return {queue['name']
            for queues in (inspector.active_queues() or {}).values()
            for queue in queues}


def get_active_igwn_alert_topics(inspector):
    return {node for stat in inspector.stats().values()
            for node in stat.get('igwn-alert-topics', ())}


def get_expected_queues(app):
    # Get the queues for all registered tasks.
    result = {getattr(task, 'queue', None) for task in app.tasks.values()}
    # We use 'celery' for all tasks that do not explicitly specify a queue.
    result -= {None}
    result |= {'celery'}
    # Done.
    return result


def get_expected_igwn_alert_topics(app):
    return app.conf['igwn_alert_topics']


def get_active_voevent_peers(inspector):
    stats = inspector.stats()
    broker_peers, receiver_peers = (
        {peer for stat in stats.values() for peer in stat.get(key, ())}
        for key in ['voevent-broker-peers', 'voevent-receiver-peers'])
    return broker_peers, receiver_peers


def get_expected_kafka_bootstep_urls(inspector):
    stats = inspector.stats()
    expected_kafka_urls = \
        {peer for stat in stats.values() for peer in
         stat.get('kafka_topic_up', {})}
    return expected_kafka_urls


def get_active_kafka_bootstep_urls(inspector):
    stats = inspector.stats()
    active_kafka_urls = \
        {kafka_url for stat in stats.values() for kafka_url, active_flag in
         stat.get('kafka_topic_up', {}).items() if active_flag}
    return active_kafka_urls


def get_undelivered_message_urls(inspector):
    stats = inspector.stats()
    undelievered_messages = \
        {kafka_url for stat in stats.values() for kafka_url, active_flag in
         stat.get('kafka_delivery_failures', {}).items() if active_flag}
    return undelievered_messages


def check_status(app):
    connection = app.connection()
    try:
        connection.ensure_connection(max_retries=1)
    except kombu.exceptions.OperationalError as e:
        raise NagiosCriticalError('No connection to broker') from e

    inspector = app.control.inspect()

    active = get_active_queues(inspector)
    expected = get_expected_queues(app)
    missing = expected - active
    if missing:
        raise NagiosCriticalError('Not all expected queues are active') from \
              AssertionError('Missing queues: ' + ', '.join(missing))

    active = get_active_igwn_alert_topics(inspector)
    expected = get_expected_igwn_alert_topics(app)
    missing = expected - active
    extra = active - expected
    if missing:
        raise NagiosCriticalError('Not all IGWN alert topics are subscribed') \
            from AssertionError('Missing topics: ' + ', '.join(missing))
    if extra:
        raise NagiosCriticalError(
            'Too many IGWN alert topics are subscribed') from AssertionError(
                    'Extra topics: ' + ', '.join(extra))

    broker_peers, receiver_peers = get_active_voevent_peers(inspector)
    if app.conf['voevent_broadcaster_whitelist'] and not broker_peers:
        raise NagiosCriticalError(
            'The VOEvent broker has no active connections') \
                from AssertionError('voevent_broadcaster_whitelist: {}'.format(
                    app.conf['voevent_broadcaster_whitelist']))
    if app.conf['voevent_receiver_address'] and not receiver_peers:
        raise NagiosCriticalError(
            'The VOEvent receiver has no active connections') \
                from AssertionError('voevent_receiver_address: {}'.format(
                    app.conf['voevent_receiver_address']))

    active = get_active_kafka_bootstep_urls(inspector)
    expected = get_expected_kafka_bootstep_urls(inspector)
    missing = expected - active
    if missing:
        raise NagiosCriticalError('Not all Kafka bootstep URLs are active') \
            from AssertionError('Missing urls: ' + ', '.join(missing))

    undelivered_messages = get_undelivered_message_urls(inspector)
    if undelivered_messages:
        raise NagiosCriticalError(
            'Not all Kafka messages have been succesfully delivered'
        ) from AssertionError(
                'URLs with undelivered messages: ' + ', '.join(missing)
        )


@click.command(help=__doc__)
@click.pass_context
def nagios(ctx):
    try:
        check_status(ctx.obj.app)
    except NagiosCriticalError as e:
        status = NagiosPluginStatus.CRITICAL
        output, = e.args
        e = e.__cause__
        detail = ''.join(format_exception(type(e), e, e.__traceback__))
    except:  # noqa: E722
        status = NagiosPluginStatus.UNKNOWN
        output = 'Unexpected error'
        detail = format_exc()
    else:
        status = NagiosPluginStatus.OK
        output = 'Running normally'
        detail = None
    print('{}: {}'.format(status.name, output))
    if detail:
        print(detail)
    exit(status)
