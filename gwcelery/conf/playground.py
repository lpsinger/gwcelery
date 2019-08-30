"""Application configuration for ``gracedb-playground.ligo.org``."""

from . import *  # noqa: F401, F403

sentry_environment = 'playground'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`)` in Sentry log
messages."""

mock_events_simulate_multiple_uploads = True
"""If True, then upload each mock event several times in rapid succession with
random jitter in order to simulate multiple pipeline uploads."""

orchestrator_timeout = 120.0
"""The orchestrator will wait this many seconds from the time of the
creation of a new superevent to the time that annotations begin, in order
to let the superevent manager's decision on the preferred event
stabilize."""
