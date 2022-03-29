"""Embed a :doc:`comet:index` LVAlert listener into a Celery worker by
:doc:`extending Celery with bootsteps <celery:userguide/extending>`.
"""
from click import Option

from .bootsteps import Receiver


def install(app):
    """Register the LVAlert subsystem in the application boot steps."""
    app.steps['consumer'] |= {Receiver}
    app.user_options['worker'].add(Option(('--igwn-alert',),
                                          is_flag=True,
                                          help='Enable IGWN Alert receiver'))
