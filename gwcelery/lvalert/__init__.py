"""Embed a :doc:`comet:index` LVAlert listener into a Celery worker by
:doc:`extending Celery with bootsteps <celery:userguide/extending>`.
"""
from .bootsteps import Receiver


def add_worker_arguments(parser):
    parser.add_argument(
        '--lvalert', action='store_true', help='Enable LVAlert receiver')


def install(app):
    """Register the LVAlert subsystem in the application boot steps."""
    app.steps['consumer'] |= {Receiver}
    app.user_options['worker'].add(add_worker_arguments)
