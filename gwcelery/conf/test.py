"""Application configuration for ``gracedb-test.ligo.org``.

Inherits all settings from :mod:`gwcelery.conf.playground`, with the exceptions
below.
"""
from . import *  # noqa: F401, F403

igwn_alert_group = 'gracedb-test'
"""IGWN alert group."""

gracedb_host = 'gracedb-test.ligo.org'
"""GraceDB host."""

kafka_urls = {
    'scimma': 'kafka://kafka.scimma.org/igwn.gwalert-test'
}
"""Kafka broker URLs"""

sentry_environment = 'test'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`_ in Sentry log
messages."""

mock_events_simulate_multiple_uploads = True
"""If True, then upload each mock event several times in rapid succession with
random jitter in order to simulate multiple pipeline uploads."""
