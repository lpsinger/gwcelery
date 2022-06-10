"""Celery application initialization."""

import sys

from celery import Celery

from ._version import get_versions
from .conf import playground
from . import email
from . import igwn_alert
from . import kafka
from . import sentry
from . import voevent

__all__ = ('app',)

__version__ = get_versions()['version']
del get_versions

# Use redis broker, because it supports locks (and thus singleton tasks).
app = Celery(__name__, broker='redis://', config_source=playground)
"""Celery application object."""

# Register email, LVAlert and VOEvent subsystems.
email.install(app)
igwn_alert.install(app)
voevent.install(app)
kafka.install(app)

# Register all tasks.
app.autodiscover_tasks([__name__])

# Customize configuration from environment variable.
app.config_from_envvar('CELERY_CONFIG_MODULE', silent=True)

# Use the same URL for both the result backend and the broker.
app.conf['result_backend'] = app.conf.broker_url

sentry.configure()


def main(argv=None):
    if argv is None:
        argv = sys.argv
    argv = argv[1:]  # Strip off the script name; click doesn't want it.
    app.start(argv)  # The application can take it from here!
