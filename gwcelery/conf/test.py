"""Application configuration for ``gracedb-test.ligo.org``.

Inherits all settings from :mod:`gwcelery.conf.playground`, with the exceptions
below.
"""

from base64 import b64encode

from . import *  # noqa: F401, F403

igwn_alert_group = 'gracedb-test'
"""IGWN alert group."""

gracedb_host = 'gracedb-test.ligo.org'
"""GraceDB host."""

kafka_alert_config = {
    'scimma': {'url': 'kafka://kafka.scimma.org/igwn.gwalert-test',
               'suffix': 'avro', 'skymap_encoder': lambda _: _},
    'gcn': {'url': 'kafka://kafka.dev.gcn.nasa.gov/igwn.gwalert',
            'suffix': 'json', 'skymap_encoder': lambda b:
            b64encode(b).decode('utf-8')}
}
"""Kafka broker configuration details"""

sentry_environment = 'test'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`_ in Sentry log
messages."""

mock_events_simulate_multiple_uploads = True
"""If True, then upload each mock event several times in rapid succession with
random jitter in order to simulate multiple pipeline uploads."""
