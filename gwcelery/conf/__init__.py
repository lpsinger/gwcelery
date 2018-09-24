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

# Celery application settings.
# Use pickle serializer, because it supports byte values.

accept_content = ['json', 'pickle']
event_serializer = 'json'
result_serializer = 'pickle'
task_serializer = 'pickle'

# GWCelery-specific settings.

lvalert_host = 'lvalert.cgca.uwm.edu'
"""LVAlert host."""

gracedb_host = 'gracedb.ligo.org'
"""GraceDb host."""

gcn_broker_address = ':5341'
"""The VOEvent broker will bind to this address to send GCNs.
This should be a string of the form `host:port`. If `host` is empty,
then listen on all available interfaces."""

gcn_broker_accept_addresses = ['capella2.gsfc.nasa.gov']
"""List of hosts from which the broker will accept connections."""

gcn_client_address = '68.169.57.253:8096'
"""The VOEvent listener will connect to this address to receive GCNs.

We are temporarily using the pre-registered port 8096 for receiving
proprietary LIGO/Virgo alerts on emfollow.ligo.caltech.edu. This means that
the capability to receive GCNs requires setting up a site configuration in
advance with Scott Barthelmey.

Once we switch to sending public alerts exclusively, then we can switch
back to using port 8099 for anonymous access, requiring no prior site
configuration."""

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

llhoft_glob = '/dev/shm/kafka/{detector}_O2/*.gwf'
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
"""Low-latency h(t) state vector configuration. This is a dictionary
consisting of a channel and its bitmask, as defined in
:module:``detchar.py``."""

idq_channels = ['H1:IDQ-PGLITCH_OVL_32_2048',
                'L1:IDQ-PGLITCH_OVL_32_2048']
"""Low-latency iDQ p(glitch) channel names"""

idq_pglitch_thresh = 0.95
"""Minimum p(glitch) reported by iDQ required before notice is posted to
GraceDb"""

p_astro_gstlal_trigger_db = '/home/gstlalcbc/observing/3/online/trigs/H1L1-ALL_LLOID-0-2000000000.sqlite'  # noqa: E501
"""Gstlal trigger database location in CIT"""

p_astro_gstlal_ln_likelihood_threshold = 6
"""log likelihood threshold"""

p_astro_gstlal_prior_type = "Uniform"
"""Prior type to be used. Options: Uniform, Jeffreys"""
