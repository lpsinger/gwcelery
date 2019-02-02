"""Application configuration for ``gracedb-test.ligo.org``."""

from . import *  # noqa: F401, F403

lvalert_host = 'lvalert-test.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb-test.ligo.org'
"""GraceDb host."""

sentry_environment = 'test'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`)` in Sentry log
messages."""
