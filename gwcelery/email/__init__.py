"""Embed an IMAP email client into a Celery worker by :doc:`extending Celery
with bootsteps <celery:userguide/extending>`.
"""
from .bootsteps import Receiver


def add_worker_arguments(parser):
    parser.add_argument(
        '--email', action='store_true', help='Enable email client')


def install(app):
    """Register the email client subsystem in the application boot steps."""
    app.steps['consumer'] |= {Receiver}
    app.user_options['worker'].add(add_worker_arguments)
