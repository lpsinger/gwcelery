"""A `Nagios plugin <https://nagios-plugins.org/doc/guidelines.html>`_
for monitoring GWCelery."""
from enum import IntEnum
from sys import exit
from traceback import format_exc, format_exception

from celery.bin.base import Command
from celery_eternal import EternalTask
import kombu.exceptions

# Make sure that all tasks are registered
from . import tasks as _  # noqa: F401


class NagiosPluginStatus(IntEnum):
    """Nagios plugin status codes."""
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


class NagiosCriticalError(Exception):
    """An exception that maps to a Nagios status of `CRITICAL`."""


def get_expected_queues(app):
    # Get the queues for all registered tasks.
    result = {getattr(task, 'queue', None) for task in app.tasks.values()}
    # We use 'celery' for all tasks that do not explicitly specify a queue.
    result -= {None}
    result |= {'celery'}
    # Done.
    return result


def get_expected_tasks(app):
    return {name for name, task in app.tasks.items()
            if isinstance(task, EternalTask)}


def check_status(app):
    connection = app.connection()
    try:
        connection.ensure_connection(max_retries=1)
    except kombu.exceptions.OperationalError as e:
        raise NagiosCriticalError('No connection to broker') from e

    inspector = app.control.inspect()

    active = {queue['name']
              for queues in (inspector.active_queues() or {}).values()
              for queue in queues}
    expected = get_expected_queues(app)
    missing = expected - active
    if missing:
        raise NagiosCriticalError('Not all expected queues are active') from \
              AssertionError('Missing queues: ' + ', '.join(missing))

    active = {task['name']
              for tasks in inspector.active().values()
              for task in tasks}
    expected = get_expected_tasks(app)
    missing = expected - active
    if missing:
        raise NagiosCriticalError('Not all expected tasks are active') from \
              AssertionError('Missing tasks: ' + ', '.join(missing))


class NagiosCommand(Command):
    """Check Celery status for monitoring with Nagios."""

    def run(self, **kwargs):
        try:
            check_status(self.app)
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
