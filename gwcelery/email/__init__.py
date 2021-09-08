"""Embed an IMAP email client into a Celery worker by :doc:`extending Celery
with bootsteps <celery:userguide/extending>`.
"""
from click import Option

from .bootsteps import Receiver


def install(app):
    """Register the email client subsystem in the application boot steps."""
    app.steps['consumer'] |= {Receiver}
    app.user_options['worker'].add(Option(('--email',),
                                          is_flag=True,
                                          help='Enable email client'))
