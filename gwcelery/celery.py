"""Celery application initialization."""

from celery import Celery

from .config import playground

# Celery application object.
# Use redis broker, because it supports locks (and thus singleton tasks).
app = Celery('gwcelery', broker='redis://', autofinalize=False)

# Add default configuration.
app.add_defaults(playground)
app.finalize()

# Customize configuration from environment variable.
app.config_from_envvar('CELERY_CONFIG_MODULE', silent=True)

# Use the same URL for both the result backend and the broker.
app.conf['result_backend'] = app.conf.broker_url
