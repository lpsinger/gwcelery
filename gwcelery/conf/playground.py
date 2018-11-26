"""Application configuration for ``gracedb-playground.ligo.org``."""

from . import *  # noqa: F401, F403

lvalert_host = 'lvalert-playground.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb-playground.ligo.org'
"""GraceDb host."""

frame_types = {'H1': 'H1_O2_llhoft',
               'L1': 'L1_O2_llhoft',
               'V1': 'V1_O2_llhoft'}
"""Types of frames used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

channel_names = {'H1': 'H1:GDS-CALIB_STRAIN_O2Replay',
                 'L1': 'L1:GDS-CALIB_STRAIN_O2Replay',
                 'V1': 'V1:Hrec_hoft_16384Hz_O2Replay'}
"""Names of h(t) channels used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""
