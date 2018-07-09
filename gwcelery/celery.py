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

    gcn_bind_address = ''
    """Address on which to listen for outbound (sending) connections to GCN;
    empty to listen on all addresses."""

    gcn_bind_port = 5341
    """Port on which to listen for outbound (sending) connections to GCN."""

    gcn_remote_address = 'capella2.gsfc.nasa.gov'
    """Address to listen for inbound (receiving) connections to GCN."""

    superevent_d_t_start = dict(gstlal=1.0,
                                pycbc=1.0,
                                mbtaonline=1.0)
    """Pipeline based lower extent of superevent segments.
    For cwb and lib this is decided from extra attributes."""

    superevent_d_t_end = dict(gstlal=1.0,
                              pycbc=1.0,
                              mbtaonline=1.0)
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
