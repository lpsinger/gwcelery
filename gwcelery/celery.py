"""Celery application configuration."""

from celery import Celery


class Base:
    """Base application configuration."""

    # Celery application settings.
    # Use pickle serializer, because it supports byte values.

    accept_content = ['json', 'pickle']
    event_serializer = 'json'
    result_serializer = 'pickle'
    task_serializer = 'pickle'

    # GWCelery-specific settings.

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
                            'gstlal-spiir': 1.0,
                            'pycbc': 1.0,
                            'mbtaonline': 1.0}
    """Pipeline based lower extent of superevent segments.
    For cwb and lib this is decided from extra attributes."""

    superevent_d_t_end = {'gstlal': 1.0,
                          'gstal-spiir': 1.0,
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
                            'gstlal-spiir': [2, 2],
                            'pycbc': [2, 2],
                            'MBTAOnline': [2, 2],
                            'LIB': [0.5, 0.5],
                            'CWB': [0.5, 0.5],
                            'HardwareInjection': [2, 2],
                            'Swift': [2, 2],
                            'Fermi': [2, 2],
                            'SNEWS': [2, 2]}
    """Seconds before and after the superevent start and end times which the DQ
    vector check will include in its check. Pipeline dependent."""

    llhoft_glob = '/dev/shm/llhoft/{detector}_O2/*.gwf'
    """File glob for low-latency h(t) frames."""

    llhoft_state_vectors = {'H1:DMT-DQ_VECTOR': (0b11, 'all'),
                            'L1:DMT-DQ_VECTOR': (0b11, 'all'),
                            'H1:GDS-CALIB_STATE_VECTOR': (0b11, 'all'),
                            'L1:GDS-CALIB_STATE_VECTOR': (0b11, 'all'),
                            'V1:DQ_ANALYSIS_STATE_VECTOR': (0b11, 'all')}
    """Low-latency h(t) state vector configuration. This is a dictionary
    mapping channel names (e.g. ``H1:DMT-DQ_VECTOR``) to tuples consisting of a
    bitmask to be logically ANDed with the state vector, and the string ``any``
    or ``all`` to indicate how many samples in the segment must satisfy the
    bitmask."""

    p_astro_gstlal_trigger_db = '/home/gstlalcbc/observing/3/online/trigs/H1L1-ALL_LLOID-0-2000000000.sqlite'  # noqa: E501
    """Gstlal trigger database location in CIT"""

    p_astro_gstlal_ln_likelihood_threshold = 6
    """log likelihood threshold"""

    p_astro_gstlal_prior_type = "Uniform"
    """Prior type to be used. Options: Uniform, Jeffreys"""


class Production(Base):
    """Application configuration for ``gracedb.ligo.org``."""

    lvalert_host = 'lvalert.cgca.uwm.edu'
    """LVAlert host."""

    gracedb_host = 'gracedb.ligo.org'
    """GraceDb host."""


class Test(Base):
    """Application configuration for ``gracedb-test.ligo.org``."""

    lvalert_host = 'lvalert-test.cgca.uwm.edu'
    """LVAlert host."""

    gracedb_host = 'gracedb-test.ligo.org'
    """GraceDb host."""


class Development(Test):
    """Application configuration for ``gracedb-dev1.ligo.org``."""

    gracedb_host = 'gracedb-dev1.ligo.org'
    """GraceDb host."""


class Playground(Test):
    """Application configuration for ``gracedb-playground.ligo.org``."""

    gracedb_host = 'gracedb-playground.ligo.org'
    """GraceDb host."""


# Celery application object.
# Use redis broker, because it supports locks (and thus singleton tasks).
app = Celery('gwcelery', broker='redis://', config_source=Playground)

# Use the same URL for both the result backend and the broker.
app.conf['result_backend'] = app.conf.broker_url
