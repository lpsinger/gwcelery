"""Application configuration for ``gracedb.ligo.org``."""

from . import *  # noqa: F401, F403

lvalert_host = 'lvalert.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb.ligo.org'
"""GraceDb host."""

frame_types = {'H1': 'H1_llhoft',
               'L1': 'L1_llhoft',
               'V1': 'V1_llhoft'}
"""Types of frames used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

channel_names = {'H1': 'H1:GDS-CALIB_STRAIN',
                 'L1': 'L1:GDS-CALIB_STRAIN',
                 'V1': 'V1:Hrec_hoft_16384Hz'}
"""Names of h(t) channels used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

sentry_environment = 'production'
"""Record this `environment tag
<https://docs.sentry.io/enriching-error-data/environments/>`)` in Sentry log
messages."""
