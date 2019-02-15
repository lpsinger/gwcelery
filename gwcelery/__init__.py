"""Celery application initialization."""

from celery import Celery

from ._version import get_versions
from .conf import playground
from . import sentry
from . import voevent

__all__ = ('app',)

__version__ = get_versions()['version']
del get_versions

# Use redis broker, because it supports locks (and thus singleton tasks).
app = Celery(__name__, broker='redis://', autofinalize=False)
"""Celery application object."""

# Register VOEvent subsystem.
voevent.install(app)

# Register all tasks.
app.autodiscover_tasks([__name__])

# Add default configuration.
app.add_defaults(playground)
app.finalize()

# Customize configuration from environment variable.
app.config_from_envvar('CELERY_CONFIG_MODULE', silent=True)

# Use the same URL for both the result backend and the broker.
app.conf['result_backend'] = app.conf.broker_url

sentry.configure()
