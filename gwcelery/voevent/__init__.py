"""Embed a :doc:`comet:index` VOEvent broker and subscriber into a Celery
worker by :doc:`extending Celery with bootsteps
<celery:userguide/extending>`."""
from .bootsteps import Reactor, Broadcaster, Receiver


def install(app):
    """Register the VOEvent subsystem in the application boot steps."""
    app.steps['consumer'] |= {Reactor, Broadcaster, Receiver}
