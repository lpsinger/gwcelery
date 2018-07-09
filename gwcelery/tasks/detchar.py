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


def read_gwf(ifo, channel, start, end):
    """Find .gwf files and create cache, then output as time series.
    This is inclusive of the start time and exclusive of the end time, i.e.
    [start, ..., end).

    Parameters
    ----------
    ifo : str
        Interferometer name (e.g. ``H1``).
    channel : str
        Channel to look at minus observatory code, ie 'DMT-DQ_VECTOR'.
    start, end : int or float
        GPS start and end times desired.

    Returns
    -------
    :class:`gwpy.timeseries.TimeSeries`

    Example
    -------
    >>> read_gwf('H1', 'DMT-DQ_VECTOR', 1214606036, 1214606040)
    <TimeSeries([7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]
                unit=Unit(dimensionless),
                t0=<Quantity 1.21460604e+09 s>,
                dt=<Quantity 0.0625 s>,
                name='H1:DMT-DQ_VECTOR',
                channel=<Channel("H1:DMT-DQ_VECTOR", 16.0 Hz) at 0x7f8ceef5a4a
                8>)>

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
    cache = Cache.from_urls(filenames)
    return TimeSeries.read(cache, ifo + ':' + channel, start=start, end=end)


def check_vector(channel, start, end, bitmask, logic_type):
    """Check timeseries of decimals against a bitmask.

    Parameters
    ----------
    channel : str
        Channel to look at, e.g. ``H1:DMT-DQ_VECTOR``.
    start, end : int or float
        GPS start and end times desired.
    bitmask : binary integer
        Bitmask which needs to be 1 in order for the timeseries to pass.
        Example: 0b11 means the 0th and 1st bits need to be 1.
    logic_type : str
        Type of logic to apply for vetoing.
        If ``all``, then all samples in the window must pass the bitmask.
        If ``any``, then one or more samples in the window must pass.

    Returns
    -------
    bool
        True if passes, False otherwise.

    Example
    -------
    >>> check_vector('H1:DMT-DQ_VECTOR', 1214606036, 1214606040, 0b11, 'all')
    True

    Notes
    -----

    For timeseries of under ~300 samples, it is slightly more
    efficient to check each sample in the series instead of checking the
    entire series, as is done here.

    In addition, with the current configuration of start and end, this
    code would have missed the glitch in L1 just before GW170817, since it
    occurred ~0.5 seconds before the start time. Currently, this code is
    called in orchestrator.py with the start and end times of the superevent,
    which would not encompass the pre-GW170817 glitch. Here is how a fix
    would be implemented:

    :func:`check_vector` would gain two parameters:
    ``check_vector(..., start, end, ..., prepeek=0, postpeek=0)``
    where ``prepeek`` and ``postpeek`` refer to durations before and after the
    superevent respectively. These would be configured as "vector_prepeek"
    and "vector_postpeek" in gwcelery/gwcelery/celery.py, and would be
    forced to be positive ints or floats. Note that the default will be
    zero, i.e. taking the superevent's start and end times.

    In the code of :func:`check_vector`, :func:`read_gwf` will read
    ``read_gwf(channel, start - prepeek, end + postpeek)``.

    In orchestrator.py, where this function is called, two new parameters
    will be called. They would sit after the bitmask ``0b11``
    and would be ``app.conf['vector_prepeek']`` and
    ``app.conf['vector_postpeek']`` respectively.
    """
    if logic_type not in ('any', 'all'):
        raise ValueError("logic_type must be either 'all' or 'any'.")

    try:
        timeseries = read_gwf(*channel.split(':'), start, end)
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
    """Perform data quality checks for an event."""
    # Skip MDC events.
    if event['search'] == 'MDC':
        log.info('Skipping state vector checks because %s is an MDC',
                 event['graceid'])
        return

    instruments = event['instruments'].split(',')

    states = {key: check_vector(key, start, end, *value)
              for key, value in app.conf['llhoft_state_vectors'].items()
              if key.split(':')[0] in instruments}

    if None in states.values():
        overall_state = None
    elif False in states.values():
        overall_state = False
    else:
        assert all(states.values())
        overall_state = True

    fmt = 'detector state is {}: channels good ({}), bad ({}), unknown ({})'
    msg = fmt.format(
        {None: 'unknown', False: 'bad', True: 'good'}[overall_state],
        ', '.join(k for k, v in states.items() if v is True),
        ', '.join(k for k, v in states.items() if v is False),
        ', '.join(k for k, v in states.items() if v is None),
    )

    gracedb.client.writeLog(superevent_id, msg, tag_name=['data_quality'])

    if overall_state is True:
        gracedb.create_label('DQOK', superevent_id)
    elif overall_state is False:
        gracedb.create_label('DQV', superevent_id)
        # Halt further proessing of canvas
        raise Ignore('vetoed by state vector')
    return event
