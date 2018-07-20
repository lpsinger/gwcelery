"""Data quality and detector characterization tasks.

These tasks are mostly focused on checking interferometer state vectors. By
design, the [LIGO]_ and [Virgo]_ state vectors share the same definitions for
the first 8 fields.

LIGO also has a [DMT]_ DQ vector that provides some additional instrumental
checks.

References
----------
.. [LIGO] https://wiki.ligo.org/Calibration/TDCalibReview
.. [Virgo] https://dcc.ligo.org/G1801125/
.. [DMT] https://wiki.ligo.org/DetChar/DmtDqVector
"""
import glob

from celery.exceptions import Ignore
from celery.utils.log import get_task_logger
from glue.lal import Cache
from gwpy.timeseries import TimeSeries
import numpy as np

from ..celery import app
from . import gracedb

__author__ = 'Geoffrey Mo <geoffrey.mo@ligo.org>'

log = get_task_logger(__name__)


def create_cache(ifo):
    """Find .gwf files and create cache.

    Parameters
    ----------
    ifo : str
        Interferometer name (e.g. ``H1``).

    Returns
    -------
    :class:`glue.lal.Cache`

    Example
    -------
    >>> create_cache('H1')
    [<glue.lal.CacheEntry at 0x7fbae6b71278>,
      <glue.lal.CacheEntry at 0x7fbae6ae5b38>,
      <glue.lal.CacheEntry at 0x7fbae6ae5c50>,
     ...
      <glue.lal.CacheEntry at 0x7fbae6b15080>,
      <glue.lal.CacheEntry at 0x7fbae6b15828>]

    Note that running this example will return an I/O error, since /dev/shm
    gets overwritten every 300 seconds.

    Notes
    -----
    There are two main ways which this function can fail, which need to
    be accounted for in the future. The first is that the directory
    (typically /dev/shm/llhoft) is found, but the files in question
    corresponding to the timestamp are not in place. This can happen if the
    function is late to the game, and hence the data have been deleted from
    memory and are no longer stored in /dev/shm/llhoft. It can also happen if
    through some asynchronous processes, the call is early, and the data files
    have not yet been written to /dev/shm/llhoft. The second way is if
    /dev/shm/llhoft is not found and hence data never shows up.

    In these cases, the desired behaviour will be for the function to wait a
    period of ~5 seconds and try again. If it still returns an I/O error of
    this type, then the function will return a flag and stop trying (this can
    happen by setting a maximum number of retries to 1).

    This is important for if gwcelery is run locally (and not on a cluster),
    where /dev/shm is inaccessible.
    """
    pattern = app.conf['llhoft_glob'].format(detector=ifo)
    filenames = glob.glob(pattern)
    return Cache.from_urls(filenames)


def check_vector(cache, channel, start, end, bitmask, logic_type='all'):
    """Check timeseries of decimals against a bitmask.
    This is inclusive of the start time and exclusive of the end time, i.e.
    [start, ..., end).

    Parameters
    ----------
    cache : :class:`glue.lal.Cache`
        Cache from which to check.
    channel : str
        Channel to look at, e.g. ``H1:DMT-DQ_VECTOR``.
    start, end : int or float
        GPS start and end times desired.
    bitmask : binary integer
        Bitmask which needs to be 1 in order for the timeseries to pass.
        Example: 0b11 means the 0th and 1st bits need to be 1.
    logic_type : str, optional
        Type of logic to apply for vetoing.
        If ``all``, then all samples in the window must pass the bitmask.
        If ``any``, then one or more samples in the window must pass.

    Returns
    -------
    bool
        True if passes, False otherwise.

    Example
    -------
    Using ``cache`` as output from example in :func:`create_cache`

    >>> check_vector(cache, 'H1:DMT-DQ_VECTOR', 1215370032, 1215370034,
                     0b11, 'all')
    True

    Notes
    -----
    For timeseries of under ~300 samples, it is slightly more
    efficient to check each sample in the series instead of checking the
    entire series, as is done here.
    """
    if logic_type not in ('any', 'all'):
        raise ValueError("logic_type must be either 'all' or 'any'.")

    try:
        timeseries = TimeSeries.read(cache, channel, start=start, end=end)
    except IndexError:
        # FIXME: figure out how to get access to low-latency frames outside
        # of the cluster. Until we figure that out, actual I/O errors have
        # to be non-fatal.
        log.exception('Failed to read from low-latency frame files')
        return None

    # FIXME: Explicitly cast to Python bool because ``np.all([1]) is True``
    # does not evaluate to True
    return bool(getattr(np, logic_type)(timeseries.value & bitmask == bitmask))


@app.task(shared=False)
def check_vectors(event, superevent_id, start, end):
    """Perform data quality checks for an event. This includes checking the DQ
    overflow vector (DMT-DQ_VECTOR) for LIGO and the first and second bits of
    the calibration state vectors for LIGO (GDS-CALIB_STATE_VECTOR) and Virgo
    (DQ_ANALYSIS_STATE_VECTOR). These vectors and the bitmasks for each are
    defined in dictionaries in ``celery.py``.

    The results of these checks are logged into the superevent specified
    by ``superevent_id``, and ``DQOK`` or ``DQV`` labels are appended
    as appropriate.

    This skips MDC events.

    Parameters
    ----------
    event : dict
        Details of event.
    superevent_id : str
        GraceID of event to which to log.
    start, end : int or float
        GPS start and end times desired.

    Returns
    -------
    event : dict
        Details of event.
    """
    # Skip MDC events.
    if event.get('search') == 'MDC':
        log.info('Skipping state vector checks because %s is an MDC',
                 event['graceid'])
        return event

    instruments = event['instruments'].split(',')
    pre, post = app.conf['check_vector_prepost'][event['pipeline']]
    start, end = start - pre, end + post

    ifos = {key.split(':')[0] for key in
            app.conf['llhoft_state_vectors'].keys()}
    caches = {ifo: create_cache(ifo) for ifo in ifos}
    states = {key: check_vector(caches[key.split(':')[0]], key, start,
                                end, *value)
              for key, value in app.conf['llhoft_state_vectors'].items()}
    active_states = {key: value for key, value in states.items()
                     if key.split(':')[0] in instruments}

    if None in active_states.values():
        overall_active_state = None
    elif False in active_states.values():
        overall_active_state = False
    else:
        assert all(active_states.values())
        overall_active_state = True

    fmt = """detector state for active instruments is {}. For all instruments,
    channels good ({}), bad ({}), unknown ({})"""
    msg = fmt.format(
        {None: 'unknown', False: 'bad', True: 'good'}[overall_active_state],
        ', '.join(k for k, v in states.items() if v is True),
        ', '.join(k for k, v in states.items() if v is False),
        ', '.join(k for k, v in states.items() if v is None),
    )

    gracedb.client.writeLog(superevent_id, msg, tag_name=['data_quality'])

    if overall_active_state is True:
        gracedb.create_label('DQOK', superevent_id)
    elif overall_active_state is False:
        gracedb.create_label('DQV', superevent_id)
        # Halt further proessing of canvas
        raise Ignore('vetoed by state vector')
    return event
