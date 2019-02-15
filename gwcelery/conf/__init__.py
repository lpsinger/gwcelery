"""GWCelery application configuration.

This module defines configuration variables and default values, including both
:doc:`generic options for Celery <celery:userguide/configuration>` as well as
options that control the behavior of specific GWCelery :mod:`~gwcelery.tasks`.

To override the configuration, define the ``CELERY_CONFIG_MODULE`` environment
variable to the fully qualified name of any Python module that can be located
in :obj:`sys.path`, including any of the following presets:

 * :mod:`gwcelery.conf.development`
 * :mod:`gwcelery.conf.playground` (the default)
 * :mod:`gwcelery.conf.production`
 * :mod:`gwcelery.conf.test`
"""

import getpass
import os

# Celery application settings.
# Use pickle serializer, because it supports byte values.

accept_content = ['json', 'pickle']
event_serializer = 'json'
result_serializer = 'pickle'
task_serializer = 'pickle'

# GWCelery-specific settings.

lvalert_host = 'lvalert-playground.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb-playground.ligo.org'
"""GraceDb host."""

voevent_broadcaster_address = ':5342'
"""The VOEvent broker will bind to this address to send GCNs.
This should be a string of the form `host:port`. If `host` is empty,
then listen on all available interfaces."""

voevent_broadcaster_whitelist = ['127.0.0.0/8']
"""List of hosts from which the broker will accept connections.
If empty, then completely disable the broker's broadcast capability."""

voevent_receiver_address = '68.169.57.253:8099'
"""The VOEvent listener will connect to this address to receive GCNs.
If empty, then completely disable the GCN listener."""

superevent_d_t_start = {'gstlal': 1.0,
                        'spiir': 1.0,
                        'pycbc': 1.0,
                        'mbtaonline': 1.0}
"""Pipeline based lower extent of superevent segments.
For cwb and lib this is decided from extra attributes."""

superevent_d_t_end = {'gstlal': 1.0,
                      'spiir': 1.0,
                      'pycbc': 1.0,
                      'mbtaonline': 1.0}
"""Pipeline based upper extent of superevent segments
For cwb and lib this is decided from extra attributes."""

superevent_query_d_t_start = 100.
"""Lower extent of superevents query"""

superevent_query_d_t_end = 100.
"""Upper extent of superevents query"""

superevent_default_d_t_start = 1.0
"""Default lower extent of superevent segments"""

superevent_default_d_t_end = 1.0
"""Default upper extent for superevent segments"""

superevent_far_threshold = 1 / 3600
"""Maximum false alarm rate to consider events superevents."""

preliminary_alert_far_threshold = {'cbc': 1 / (30 * 86400),
                                   'burst': 1 / (365 * 86400),
                                   'test': 1 / (30 * 86400)}
"""Group specific maximum false alarm rate to consider
sending preliminary alerts."""

preliminary_alert_trials_factor = dict(cbc=5.0, burst=5.0)
"""Trials factor corresponding to trigger categories.
For CBC, trials factor is the number of pipelines plus the external
coincidence search. For Burst, this is the total number of searches
plus the external coincidence search.
CBC pipelines are gstlal, pycbc, mbtaonline, spiir.
Burst searches are cwb.allsky, cwb.bbh, cwb.imbh and olib.allsky."""

orchestrator_timeout = 15.0
"""The orchestrator will wait this many seconds from the time of the
creation of a new superevent to the time that annotations begin, in order
to let the superevent manager's decision on the preferred event
stabilize."""

check_vector_prepost = {'gstlal': [2, 2],
                        'spiir': [2, 2],
                        'pycbc': [2, 2],
                        'MBTAOnline': [2, 2],
                        'oLIB': [0.5, 0.5],
                        'LIB': [0.5, 0.5],
                        'CWB': [0.5, 0.5],
                        'HardwareInjection': [2, 2],
                        'Swift': [2, 2],
                        'Fermi': [2, 2],
                        'SNEWS': [2, 2]}
"""Seconds before and after the superevent start and end times which the DQ
vector check will include in its check. Pipeline dependent."""

uses_gatedhoft = {'gstlal': False,
                  'spiir': True,
                  'pycbc': True,
                  'MBTAOnline': True,
                  'oLIB': False,
                  'LIB': False,
                  'CWB': True,
                  'HardwareInjection': False,
                  'Swift': False,
                  'Fermi': False,
                  'SNEWS': False}
"""Whether or not a pipeline uses gated h(t). Determines whether or not
the DMT-DQ_VECTOR will be analyzed for data quality."""

llhoft_glob = '/dev/shm/llhoft/{detector}/*.gwf'
"""File glob for low-latency h(t) frames."""

llhoft_channels = {
    'H1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
    'L1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
    'H1:GDS-CALIB_STATE_VECTOR': 'state_vector_bits',
    'L1:GDS-CALIB_STATE_VECTOR': 'state_vector_bits',
    'V1:DQ_ANALYSIS_STATE_VECTOR': 'state_vector_bits',
    #  Virgo DQ veto streams, should be implemented before September O2 replay
    #  'V1:DQ_VETO_MBTA': 'no_dq_veto_mbta_bits',
    #  'V1:DQ_VETO_CWB': 'no_dq_veto_cwb_bits',
    #  'V1:DQ_VETO_GSTLAL': 'no_dq_veto_gstlal_bits',
    #  'V1:DQ_VETO_OLIB': 'no_dq_veto_olib_bits',
    #  'V1:DQ_VETO_PYCBC': 'no_dq_veto_pycbc_bits',
                  }
"""Low-latency h(t) state vector configuration. This is a dictionary consisting
of a channel and its bitmask, as defined in :mod:`gwcelery.tasks.detchar`."""

idq_channels = ['H1:IDQ-PGLITCH_RANDOM_FOREST_16_4096',
                'L1:IDQ-PGLITCH_RANDOM_FOREST_16_4096']
"""Low-latency iDQ p(glitch) channel names"""

idq_pglitch_thresh = 0.95
"""Minimum p(glitch) reported by iDQ required before notice is posted to
GraceDb"""

p_astro_gstlal_ln_likelihood_threshold = 6
"""log likelihood threshold"""

p_astro_gstlal_ranking_pdf = '/home/gstlalcbc/observing/3/online/trigs/rankingstat_pdf.xml.gz'  # noqa: E501

p_astro_url = \
    'http://emfollow.ldas.cit/data/H1L1V1-mean_counts-1126051217-61603201.json'
"""URL for mean values of Poisson counts using which p_astro
is computed. (Used by :mod:`gwcelery.tasks.p_astro_gstlal` and
:mod:`gwcelery.tasks.p_astro_other`)
"""

low_latency_frame_types = {'H1': 'H1_O2_llhoft',
                           'L1': 'L1_O2_llhoft',
                           'V1': 'V1_O2_llhoft'}
"""Types of frames used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

high_latency_frame_types = {'H1': 'None',
                            'L1': 'None',
                            'V1': 'None'}
"""Types of nonllhoft-frames used in Parameter Estimation with LALInference.
They do not exist for O2Replay data. (see
:mod:`gwcelery.tasks.lalinference`)"""

strain_channel_names = {'H1': 'H1:GDS-CALIB_STRAIN_O2Replay',
                        'L1': 'L1:GDS-CALIB_STRAIN_O2Replay',
                        'V1': 'V1:Hrec_hoft_16384Hz_O2Replay'}
"""Names of h(t) channels used in Parameter Estimation with LALInference (see
:mod:`gwcelery.tasks.lalinference`)"""

state_vector_channel_names = {'H1': 'H1:GDS-CALIB_STATE_VECTOR',
                              'L1': 'L1:GDS-CALIB_STATE_VECTOR',
                              'V1': 'V1:DQ_ANALYSIS_STATE_VECTOR'}
"""Names of state vector channels used in Parameter Estimation with
LALInference (see :mod:`gwcelery.tasks.lalinference`)"""

pe_threshold = 1.0 / (14 * 86400)
"""FAR threshold in Hz for Parameter Estimation. PE group now applies
1/(2 weeks) as a threshold. 86400 seconds = 1 day and 14 days = 2 weeks."""

pe_results_path = os.path.join(os.getenv('HOME'), 'public_html/online_pe')
"""Path to the results of Parameter Estimation (see
:mod:`gwcelery.tasks.lalinference`)"""

pe_results_url = ('https://ldas-jobs.ligo.caltech.edu/~{}/'
                  'online_pe/').format(getpass.getuser())
"""URL of page where all the results of Parameter Estimation are outputted
(see :mod:`gwcelery.tasks.lalinference`)"""
