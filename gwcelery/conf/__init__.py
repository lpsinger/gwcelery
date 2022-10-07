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

# Task tombstones expire after 2 hours.
# Celery's default setting of 1 day could cause the Redis database to grow too
# large because we pass large byte strings as task arguments and return values.
result_expires = 7200

# Use pickle serializer, because it supports byte values.
accept_content = ['json', 'pickle']
event_serializer = 'json'
result_serializer = 'pickle'
task_serializer = 'pickle'

# Compress tasks to reduce bandwidth in and out of Redis.
result_compression = task_compression = 'zstandard'

# Task priority settings.
task_inherit_parent_priority = True
task_default_priority = 0
task_queue_max_priority = 1
broker_transport_options = {
    'priority_steps': list(range(task_queue_max_priority + 1))
}

worker_proc_alive_timeout = 8
"""The timeout when waiting for a new worker process to start up."""

worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s/%(threadName)s] %(message)s"  # noqa: E501
"""Custom worker log format that includes the thread name."""

# GWCelery-specific settings.

condor_accounting_group = 'ligo.dev.o3.cbc.pe.bayestar'
"""HTCondor accounting group for Celery workers launched with condor_submit."""

expose_to_public = False
"""Set to True if events meeting the public alert threshold really should be
exposed to the public."""

igwn_alert_group = 'gracedb-playground'
"""IGWN alert group."""

gracedb_host = 'gracedb-playground.ligo.org'
"""GraceDB host."""

voevent_broadcaster_address = ':5342'
"""The VOEvent broker will bind to this address to send GCNs.
This should be a string of the form `host:port`. If `host` is empty,
then listen on all available interfaces."""

voevent_broadcaster_whitelist = []
"""List of hosts from which the broker will accept connections.
If empty, then completely disable the broker's broadcast capability."""

voevent_receiver_address = '68.169.57.253:8099'
"""The VOEvent listener will connect to this address to receive GCNs. For
options, see `GCN's list of available VOEvent servers
<https://gcn.gsfc.nasa.gov/voevent.html#tc2>`_. If this is an empty string,
then completely disable the GCN listener."""

email_host = 'imap.gmail.com'
"""IMAP hostname to receive the GCN e-mail notice formats."""

superevent_d_t_start = {'gstlal': 1.0,
                        'spiir': 1.0,
                        'pycbc': 1.0,
                        'mbta': 1.0}
"""Pipeline based lower extent of superevent segments.
For cwb and lib this is decided from extra attributes."""

superevent_d_t_end = {'gstlal': 1.0,
                      'spiir': 1.0,
                      'pycbc': 1.0,
                      'mbta': 1.0}
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

preliminary_alert_timeout = 0.0
"""Wait this many seconds for the preferred event to stabilize before issuing a
preliminary alert."""

preliminary_alert_far_threshold = {'cbc': 1 / (60 * 86400),
                                   'burst': 1 / (365 * 86400),
                                   'test': 1 / (30 * 86400)}
"""Group specific maximum false alarm rate to consider
sending preliminary alerts."""

early_warning_alert_trials_factor = 2.0
"""Trials factor for early warning alerts. There are two pipelines that are
producing early warning events: gstlal and spiir."""

preliminary_alert_trials_factor = dict(cbc=5.0, burst=4.0)
"""Trials factor corresponding to trigger categories. For CBC and Burst, trials
factor is the number of pipelines. CBC pipelines are gstlal, pycbc, mbta and
spiir. Burst searches are cwb.allsky, cwb.bbh and cwb.imbh."""

early_warning_alert_far_threshold = 1 / (3600 * 24)
"""False alarm rate threshold for early warning alerts."""

snews_gw_far_threshold = 1 / (3600 * 24)
"""Maximum false alarm rate for a superevent to send out a coincidence alert
between an external SNEWS alert and the superevent."""

superevent_clean_up_timeout = 270.
"""The orchestrator will wait this many seconds from the time of the
application of the GCN_PRELIM_SENT label to revise the preferred
event out of the accumulated events."""

subthreshold_annotation_timeout = 300.
"""The orchestrator will wait this many seconds from the time of the
creation of a new superevent to the time that subthreshold superevents
are annotated. It is expected that the timeout is long enough such
that there are no more G events being added to the superevent."""

pe_timeout = 345.0
"""The orchestrator will wait this many seconds from the time of the
creation of a new superevent to the time that parameter estimation begins, in
case the preferred event is updated with high latency."""

check_vector_prepost = {'gstlal': [2, 2],
                        'spiir': [2, 2],
                        'pycbc': [2, 2],
                        'MBTA': [2, 2],
                        'oLIB': [1.5, 1.5],
                        'LIB': [1.5, 1.5],
                        'CWB': [1.5, 1.5],
                        'HardwareInjection': [2, 2],
                        'Swift': [2, 2],
                        'Fermi': [2, 2],
                        'INTEGRAL': [2, 2],
                        'AGILE': [2, 2],
                        'SNEWS': [10, 10]}
"""Seconds before and after the superevent start and end times which the DQ
vector check will include in its check. Pipeline dependent."""

uses_gatedhoft = {'gstlal': True,
                  'spiir': True,
                  'pycbc': True,
                  'MBTA': True,
                  'oLIB': False,
                  'LIB': False,
                  'CWB': True,
                  'HardwareInjection': False,
                  'Swift': False,
                  'Fermi': False,
                  'INTEGRAL': False,
                  'AGILE': False,
                  'SNEWS': False}
"""Whether or not a pipeline uses gated h(t). Determines whether or not
the DMT-DQ_VECTOR will be analyzed for data quality."""

llhoft_glob = '/dev/shm/kafka/{detector}_O3ReplayMDC/*.gwf'
"""File glob for playground low-latency h(t) frames. Currently points
to O3 MDC Mock Data Challange data.
See https://git.ligo.org/emfollow/mock-data-challenge"""

llhoft_channels = {
    'H1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
    'L1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
    'H1:GDS-CALIB_STATE_VECTOR': 'ligo_state_vector_bits',
    'L1:GDS-CALIB_STATE_VECTOR': 'ligo_state_vector_bits',
    'V1:DQ_ANALYSIS_STATE_VECTOR': 'virgo_state_vector_bits'}
"""Low-latency h(t) state vector configuration. This is a dictionary consisting
of a channel and its bitmask, as defined in :mod:`gwcelery.tasks.detchar`."""

idq_channels = ['H1:IDQ-PGLITCH_OVL_16_4096',
                'L1:IDQ-PGLITCH_OVL_16_4096']
"""Low-latency iDQ p(glitch) channel names from O3 replay."""

idq_pglitch_thresh = 0.95
"""If P(Glitch) is above this threshold, and
:obj:`~gwcelery.conf.idq_veto` for the pipeline is true, DQV will be labeled
for the event.
"""

idq_veto = {'gstlal': False,
            'spiir': False,
            'pycbc': False,
            'MBTA': False,
            'oLIB': False,
            'LIB': False,
            'CWB': False,
            'HardwareInjection': False,
            'Swift': False,
            'Fermi': False,
            'INTEGRAL': False,
            'AGILE': False,
            'SNEWS': False}
"""If true for a pipeline, iDQ values above the threshold defined in
:obj:`~gwcelery.conf.idq_pglitch.thres` will cause DQV to be labeled.
Currently all False, pending iDQ review (should be done before O3).
"""

low_latency_frame_types = {'H1': 'H1_O3ReplayMDC_llhoft',
                           'L1': 'L1_O3ReplayMDC_llhoft',
                           'V1': 'V1_O3ReplayMDC_llhoft'}
"""Types of low latency frames used in Parameter Estimation (see
:mod:`gwcelery.tasks.inference`) and in cache creation for detchar
checks (see :mod:`gwcelery.tasks.detchar`).
"""

high_latency_frame_types = {'H1': None,
                            'L1': None,
                            'V1': None}
"""Types of high latency frames used in Parameter Estimation and in cache
creation for detchar checks. They do not exist for O3Replay data. (see
:mod:`gwcelery.tasks.inference` and :mod:`gwcelery.tasks.detchar`)
"""

strain_channel_names = {'H1': 'H1:GDS-CALIB_STRAIN_INJ1_O3Replay',
                        'L1': 'L1:GDS-CALIB_STRAIN_INJ1_O3Replay',
                        'V1': 'V1:Hrec_hoft_16384Hz_INJ1_O3Replay'}
"""Names of h(t) channels used in Parameter Estimation (see
:mod:`gwcelery.tasks.inference`) and in detchar omegascan creation
(see :mod:`gwcelery.tasks.detchar`)."""

state_vector_channel_names = {'H1': 'H1:GDS-CALIB_STATE_VECTOR',
                              'L1': 'L1:GDS-CALIB_STATE_VECTOR',
                              'V1': 'V1:DQ_ANALYSIS_STATE_VECTOR'}
"""Names of state vector channels used in Parameter Estimation (see
:mod:`gwcelery.tasks.inference`)"""

detchar_bit_definitions = {
    'dmt_dq_vector_bits': {
        'channel': 'DMT-DQ_VECTOR',
        'bits': {
            1: 'NO_OMC_DCPD_ADC_OVERFLOW',
            2: 'NO_DMT-ETMY_ESD_DAC_OVERFLOW'
        },
        'description': {
            'NO_OMC_DCPD_ADC_OVERFLOW': 'OMC DCPC ADC not overflowing',
            'NO_DMT-ETMY_ESD_DAC_OVERFLOW': 'ETMY ESD DAC not overflowing'
        }
    },
    'ligo_state_vector_bits': {
        'channel': 'GDS-CALIB_STATE_VECTOR',
        'bits': {
            0: 'HOFT_OK',
            1: 'OBSERVATION_INTENT',
            5: 'NO_STOCH_HW_INJ',
            6: 'NO_CBC_HW_INJ',
            7: 'NO_BURST_HW_INJ',
            8: 'NO_DETCHAR_HW_INJ'
        },
        'description': {
            'HOFT_OK': 'h(t) was successfully computed',
            'OBSERVATION_INTENT': '"observation intent" button is pushed',
            'NO_STOCH_HW_INJ': 'No stochastic HW injection',
            'NO_CBC_HW_INJ': 'No CBC HW injection',
            'NO_BURST_HW_INJ': 'No burst HW injection',
            'NO_DETCHAR_HW_INJ': 'No HW injections for detector characterization'  # noqa: E501
        }
    },
    'virgo_state_vector_bits': {
        'channel': 'DQ_ANALYSIS_STATE_VECTOR',
        'bits': {
            0: 'HOFT_OK',
            1: 'OBSERVATION_INTENT',
            5: 'NO_STOCH_HW_INJ',
            6: 'NO_CBC_HW_INJ',
            7: 'NO_BURST_HW_INJ',
            8: 'NO_DETCHAR_HW_INJ',
            10: 'GOOD_DATA_QUALITY_CAT1'
        },
        'description': {
            'HOFT_OK': 'h(t) was successfully computed',
            'OBSERVATION_INTENT': '"observation intent" button is pushed',
            'NO_STOCH_HW_INJ': 'No stochastic HW injection',
            'NO_CBC_HW_INJ': 'No CBC HW injection',
            'NO_BURST_HW_INJ': 'No burst HW injection',
            'NO_DETCHAR_HW_INJ': 'No HW injections for detector characterization',  # noqa: E501
            'GOOD_DATA_QUALITY_CAT1': 'Good data quality (CAT1 type)'
        }
    }
}
"""Bit definitions for detchar checks"""

omegascan_durations = [0.5, 2.0, 10.0]
"""Durations for omegascans, symmetric about t0"""

pe_results_path = os.path.join(os.getenv('HOME'), 'public_html/online_pe')
"""Path to the results of Parameter Estimation (see
:mod:`gwcelery.tasks.inference`)"""

pe_results_url = ('https://ldas-jobs.ligo.caltech.edu/~{}/'
                  'online_pe/').format(getpass.getuser())
"""URL of page where all the results of Parameter Estimation are outputted
(see :mod:`gwcelery.tasks.inference`)"""

raven_coincidence_windows = {'GRB_CBC': [-5, 1],
                             'GRB_CBC_SubFermi': [-11, 1],
                             'GRB_CBC_SubSwift': [-20, 10],
                             'GRB_Burst': [-600, 60],
                             'SNEWS': [-10, 10]}
"""Time coincidence windows passed to ligo-raven. External events and
superevents of the appropriate type are considered to be coincident if
within time window of each other."""

mock_events_simulate_multiple_uploads = False
"""If True, then upload each mock event several times in rapid succession with
random jitter in order to simulate multiple pipeline uploads."""

only_alert_for_mdc = False
"""If True, then only sends alerts for MDC events. Useful for times outside
of observing runs."""

joint_mdc_freq = 2
"""Determines how often an external MDC event will be created near an
MDC superevent to test the RAVEN alert pipeline, i.e for every x
MDC superevents an external MDC event is created."""

# Delete imported modules so that they do not pollute the config object
del os, getpass
