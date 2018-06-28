import glob

import numpy as np
from glue.lal import Cache
from gwpy.timeseries import TimeSeries

from ..celery import app
from . import gracedb

__author__ = 'Geoffrey Mo <geoffrey.mo@ligo.org>'


def read_gwf(ifo, channel, start, end):
    """Find .gwf files and create cache, then output as time series.
    This is inclusive of the start time and exclusive of the end time, i.e.
    [start, ..., end).

    Parameters
    ----------
    ifo : str
        Name of observatory.

    channel : str
        Channel to look at minus observatory code, ie 'DMT-DQ_VECTOR'.

    start : float
        Start time

    end: float
        End time

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
    pattern = '/dev/shm/llhoft/{}/*.gwf'.format(ifo)
    filenames = glob.glob(pattern)
    source = Cache.from_urls(filenames)
    return TimeSeries.read(source, ifo+':'+channel,
                           start=start, end=end)


@app.task(shared=False)
def check_vector(ifo, channel, start, end, bitmask, logic_type):
    """Check timeseries of decimals against a bitmask.

    Parameters
    ----------
    First four parameters same as in :func:`read_gwf`.

    timeseries : :class:`gwpy.timeseries.TimeSeries`
        Timeseries to check.
    bitmask : binary integer
        Bitmask which needs to be 1 in order for the timeseries to pass.
        Example: 0b11 means the 0th and 1st bits need to be 1.
    logic_type : str
        Type of logic to apply for vetoing.
        'all' needs each entry in the timeseries to fail to veto the sample
        'any' will fail the sample upon the failure of any entry

    Returns
    -------
    bool
        True if passes, False otherwise.

    Example
    -------
    >>> check_vector('H1', 'DMT-DQ_VECTOR', 1214606036, 1214606040, 0b11,
    >>>                     'any')
    True

    Notes
    -----

    For timeseries of under ~300 samples, it is slightly more
    efficient to check each sample in the series instead of checking the
    entire series, as is done here.

    In addition, with the current configuration of start and duration, this
    code would have missed the glitch in L1 just before GW170817, since it
    occurred ~0.5 seconds before the start time. Currently, this code is
    called in orchestrator.py with the start and end times of the superevent,
    which would not encompass the pre-GW170817 glitch. Here is how a fix
    would be implemented:

    :func:`check_vector` would gain two parameters:
    check_vector(..., start, duration, ..., prepeek=0, postpeek=0)
    where "prepeek" and "postpeek" refer to durations before and after the
    superevent respectively. These would be configured as "vector_prepeek"
    and "vector_postpeek" in gwcelery/gwcelery/celery.py, and would be
    forced to be positive ints or floats. Note that the default will be
    zero, i.e. taking the superevent's start and end times.

    In the code of :func:`check_vector`, :func:`read_gwf` will read
    read_gwf(channel, ifo, start-prepeek, duration+prepeek+postpeek)

    In orchestrator.py, where this function is called, two new parameters
    will be called. They would sit after app.conf['vector_check_logic']
    and would be app.conf['vector_prepeek'] and
    app.conf['vector_postpeek'] respectively.
    """
    timeseries = read_gwf(ifo, channel, start, end)
    list_of_sample_pass = timeseries.value & bitmask == bitmask
    if logic_type == 'all':
        return np.any(list_of_sample_pass)

    elif logic_type == 'any':
        return np.all(list_of_sample_pass)

    else:
        raise ValueError("logic_type must be either 'all' or 'any'.")


@app.task(shared=False, ignore_result=True)
def check_vector_gracedb_label(check_vector_result_dict, graceid):
    """Append label to GraceDb with results of check_vector().

    Parameters
    ----------
    check_vector_result_dict : dict
        Dictionary of check_vector() results

    graceid : str
        GraceID to which to append label.

    Returns
    -------
    None
    """
    for channel in check_vector_result_dict:
        if check_vector_result_dict[channel]:
            gracedb.create_label(channel+'_PASS', graceid)
        else:
            gracedb.create_label(channel+'_FAIL', graceid)
