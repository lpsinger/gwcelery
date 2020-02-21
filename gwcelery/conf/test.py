"""Application configuration for ``gracedb-test.ligo.org``.

Inherits all settings from :mod:`gwcelery.conf.playground`, with the exceptions
below.
"""
from . import *  # noqa: F401, F403

lvalert_host = 'lvalert-test.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb-test.ligo.org'
"""GraceDB host."""

sentry_environment = 'test'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`_ in Sentry log
messages."""

mock_events_simulate_multiple_uploads = True
"""If True, then upload each mock event several times in rapid succession with
random jitter in order to simulate multiple pipeline uploads."""
