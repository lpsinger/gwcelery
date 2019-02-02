"""Application configuration for ``gracedb.ligo.org``."""

from . import *  # noqa: F401, F403

sentry_environment = 'production'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`)` in Sentry log
messages."""
