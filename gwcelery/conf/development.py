"""Application configuration for ``gracedb-dev1.ligo.org``.

Inherits all settings from :mod:`gwcelery.conf.test`, with the exceptions
below.
"""
from .test import *  # noqa: F401, F403

gracedb_host = 'gracedb-dev1.ligo.org'
"""GraceDB host."""

sentry_environment = 'development'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`_ in Sentry log
messages."""
