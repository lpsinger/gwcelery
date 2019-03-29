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
import getpass
import glob
import json
import socket
import time

from celery.utils.log import get_task_logger
from glue.lal import Cache
from gwdatafind import find_urls
from gwpy.timeseries import Bits, StateVector, TimeSeries
import numpy as np

from . import gracedb
from ..import app
from ..import _version
from ..jinja import env


__author__ = 'Geoffrey Mo <geoffrey.mo@ligo.org>'

log = get_task_logger(__name__)

dmt_dq_vector_bits = Bits(
    channel='DMT-DQ_VECTOR',
    bits={
        1: 'NO_OMC_DCPD_ADC_OVERFLOW',
        2: 'NO_DMT-ETMY_ESD_DAC_OVERFLOW'
    },
    description={
        'NO_OMC_DCPD_ADC_OVERFLOW': 'OMC DCPC ADC not overflowing',
        'NO_DMT-ETMY_ESD_DAC_OVERFLOW': 'ETMY ESD DAC not overflowing'
    }
)
"""DMT DQ vector bits (LIGO only)."""


ligo_state_vector_bits = Bits(
    channel='GDS-CALIB_STATE_VECTOR',
    bits={
        0: 'HOFT_OK',
        1: 'OBSERVATION_INTENT',
        5: 'NO_STOCH_HW_INJ',
        6: 'NO_CBC_HW_INJ',
        7: 'NO_BURST_HW_INJ',
        8: 'NO_DETCHAR_HW_INJ'
    },
    description={
        'HOFT_OK': 'h(t) was successfully computed',
        'OBSERVATION_INTENT': '"observation intent" button is pushed',
        'NO_STOCH_HW_INJ': 'No stochastic HW injection',
        'NO_CBC_HW_INJ': 'No CBC HW injection',
        'NO_BURST_HW_INJ': 'No burst HW injection',
        'NO_DETCHAR_HW_INJ': 'No HW injections for detector characterization'
    }
)
"""State vector bitfield definitions for LIGO."""

virgo_state_vector_bits = Bits(
    channel='DQ_ANALYSIS_STATE_VECTOR',
    bits={
        0: 'HOFT_OK',
        1: 'OBSERVATION_INTENT',
        5: 'NO_STOCH_HW_INJ',
        6: 'NO_CBC_HW_INJ',
        7: 'NO_BURST_HW_INJ',
        8: 'NO_DETCHAR_HW_INJ',
        10: 'GOOD_DATA_QUALITY_CAT1'
    },
    description={
        'HOFT_OK': 'h(t) was successfully computed',
        'OBSERVATION_INTENT': '"observation intent" button is pushed',
        'NO_STOCH_HW_INJ': 'No stochastic HW injection',
        'NO_CBC_HW_INJ': 'No CBC HW injection',
        'NO_BURST_HW_INJ': 'No burst HW injection',
        'NO_DETCHAR_HW_INJ': 'No HW injections for detector characterization',
        'GOOD_DATA_QUALITY_CAT1': 'Good data quality (CAT1 type)'
    }
)
"""State vector bitfield definitions for Virgo."""


no_dq_veto_mbta_bits = Bits(
    channel='V1:DQ_VETO_MBTA',
    bits={0: 'NO_DQ_VETO_MBTA'},
    description={'NO_DQ_VETO_MBTA': 'NO DQ veto for MBTA'}
                           )

no_dq_veto_cwb_bits = Bits(
    channel='V1:DQ_VETO_CWB', bits={0: 'NO_DQ_VETO_CWB'},
    description={'NO_DQ_VETO_CWB': 'NO DQ veto for cWB'}
                          )

no_dq_veto_gstlal_bits = Bits(
    channel='V1:DQ_VETO_GSTLAL', bits={0: 'NO_DQ_VETO_GSTLAL'},
    description={'NO_DQ_VETO_GSTLAL': 'NO DQ veto for gstLAL'}
                             )

no_dq_veto_olib_bits = Bits(
    channel='V1:DQ_VETO_OLIB', bits={0: 'NO_DQ_VETO_OLIB'},
    description={'NO_DQ_VETO_OLIB': 'NO DQ veto for oLIB'}
                           )

no_dq_veto_pycbc_bits = Bits(
    channel='V1:DQ_VETO_PYCBC',
    bits={0: 'NO_DQ_VETO_PYCBC'},
    description={'NO_DQ_VETO_PYCBC': 'NO DQ veto for pyCBC'}
                            )
"""No DQ veto stream bitfield definitions for Virgo.
NOTE: Since the results for these bits will be NOT()ed, the bit
definitions are the NO_* versions of what the bit * actually is.
This is an inelegant but the simplest solution since the logic used in these
channels are opposite to those in all the other checked channels."""


def create_cache(ifo, start, end):
    """Find .gwf files and create cache. Will first look in the llhoft, and
    if the frames have expired from llhoft, will call gwdatafind.

    Parameters
    ----------
    ifo : str
        Interferometer name (e.g. ``H1``).
    start, end: int or float
        GPS start and end times desired.

    Returns
    -------
    :class:`glue.lal.Cache`

    Example
    -------
    >>> create_cache('H1', 1198800018, 1198800618)
    [<glue.lal.CacheEntry at 0x7fbae6b71278>,
      <glue.lal.CacheEntry at 0x7fbae6ae5b38>,
      <glue.lal.CacheEntry at 0x7fbae6ae5c50>,
     ...
      <glue.lal.CacheEntry at 0x7fbae6b15080>,
      <glue.lal.CacheEntry at 0x7fbae6b15828>]
    """
    pattern = app.conf['llhoft_glob'].format(detector=ifo)
    filenames = glob.glob(pattern)
    cache = Cache.from_urls(filenames)
    try:
        cache_starttime = int(
            list(cache.to_segmentlistdict().values())[0][0][0])
    except IndexError:
        log.exception('Files do not exist in llhoft_glob')
        return cache  # returns empty cache
    if start < cache_starttime:  # required data has left llhoft
        urls = find_urls(ifo[0], '{}1_HOFT_C00'.format(ifo[0]), start, end)
        cache = Cache.from_urls(urls)
    return cache


def generate_table(title, high_bit_list, low_bit_list, unknown_bit_list):
    """Make a nice table which shows the status of the bits checked.

    Parameters
    ----------
    title : str
        Title of the table.
    high_bit_list: list
        List of bit names which are high.
    low_bit_list: list
        List of bit names which are low.
    unknown_bit_list: list
        List of bit names which are unknown.

    Returns
    -------
    str
        HTML string of the table.
    """
    template = env.get_template('vector_table.jinja2')
    return template.render(title=title, high_bit_list=high_bit_list,
                           low_bit_list=low_bit_list,
                           unknown_bit_list=unknown_bit_list)


def dqr_json(state, summary):
    """Generate DQR-compatible json-ready dictionary from process results, as
    described in :class:`data-quality-report.design`.

    Parameters
    ----------
    state : {'pass', 'fail'}
        State of the detchar checks.
    summary : str
        Summary of results from the process.

    Returns
    -------
    dict
        Ready to be converted into json.

    """
    links = [
        {
            "href":
            "https://gwcelery.readthedocs.io/en/latest/gwcelery.tasks.detchar.html#gwcelery.tasks.detchar.check_vectors", # noqa
            "innerHTML": "a link to the documentation for this process"
        },
        {
            "href":
            "https://git.ligo.org/emfollow/gwcelery/blob/master/gwcelery/tasks/detchar.py",  # noqa
            "innerHTML": "a link to the source code in the gwcelery repo"
        }
    ]
    return dict(
        state=state,
        process_name=__name__,
        process_version=_version.get_versions()['version'],
        librarian='Geoffrey Mo (geoffrey.mo@ligo.org)',
        date=time.strftime("%H:%M:%S UTC %a %d %b %Y", time.gmtime()),
        hostname=socket.gethostname(),
        username=getpass.getuser(),
        summary=summary,
        figures=[],
        tables=[],
        links=links,
        extra=[],
    )


def check_idq(cache, channel, start, end):
    """Looks for iDQ frame and reads them.

    Parameters
    ----------
    cache : :class:`glue.lal.Cache`
        Cache from which to check.
    channel : str
        which idq channel (pglitch)
    start, end: int or float
        GPS start and end times desired.

    Returns
    -------
    tuple
        Tuple mapping iDQ channel to its maximum P(glitch).

    Example
    -------
    >>> check_idq(cache, 'H1:IDQ-PGLITCH-OVL-100-1000',
                  1216496260, 1216496262)
    ('H1:IDQ-PGLITCH-OVL-100-1000', 0.87)
    """
    try:
        idq_prob = TimeSeries.read(
            cache, channel, start=start, end=end)
    except (IndexError, RuntimeError):
        # FIXME: figure out how to get access to low-latency frames outside
        # of the cluster. Until we figure that out, actual I/O errors have
        # to be non-fatal.
        log.exception('Failed to read from low-latency iDQ frame files')
        return (channel, None)
    else:
        return (channel, float(idq_prob.max()))


def check_vector(cache, channel, start, end, bits, logic_type='all'):
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
    bits: :class:`gwpy.TimeSeries.Bits`
        Definitions of the bits in the channel.
    logic_type : str, optional
        Type of logic to apply for vetoing.
        If ``all``, then all samples in the window must pass the bitmask.
        If ``any``, then one or more samples in the window must pass.

    Returns
    -------
    dict
        Maps each bit in channel to its state.

    Example
    -------
    >>> check_vector(cache, 'H1:GDS-CALIB_STATE_VECTOR', 1216496260,
                     1216496262, ligo_state_vector_bits)
    {'H1:HOFT_OK': True,
     'H1:OBSERVATION_INTENT': True,
     'H1:NO_STOCH_HW_INJ': True,
     'H1:NO_CBC_HW_INJ': True,
     'H1:NO_BURST_HW_INJ': True,
     'H1:NO_DETCHAR_HW_INJ': True}
    """
    if logic_type not in ('any', 'all'):
        raise ValueError("logic_type must be either 'all' or 'any'.")
    bitname = '{}:{}'
    try:
        statevector = StateVector.read(cache, channel, start=start, end=end,
                                       bits=bits)
    except IndexError:
        # FIXME: figure out how to get access to low-latency frames outside
        # of the cluster. Until we figure that out, actual I/O errors have
        # to be non-fatal.
        log.exception('Failed to read from low-latency frame files')
        return {bitname.format(channel.split(':')[0], key):
                None for key in bits if key is not None}
    else:
        return {bitname.format(channel.split(':')[0], key):
                bool(getattr(np, logic_type)(getattr(value, 'value')))
                for key, value in statevector.get_bit_series().items()}


@app.task(shared=False)
def check_vectors(event, graceid, start, end):
    """Perform data quality checks for an event and labels/logs results to
    GraceDb.

    Depending on the pipeline, a certain amount of time (specified in
    :obj:`~gwcelery.conf.check_vector_prepost`) is appended to either side of
    the superevent start and end time. This is to catch DQ issues slightly
    before and after the event, such as that appearing in L1 just before
    GW170817.

    A cache is then created for H1, L1, and V1, regardless of the detectors
    involved in the event. Then, the bits and channels specified in the
    configuration file (:obj:`~gwcelery.conf.llhoft_channels`) are checked.
    If an injection is found in the active detectors, 'INJ' is labeled to
    GraceDb. If an injection is found in any detector, a message with the
    injection found is logged to GraceDb. If no injections are found across
    all detectors, this is logged to GraceDb.

    A similar task is performed for the DQ states described in the
    DMT-DQ_VECTOR, LIGO GDS-CALIB_STATE_VECTOR, and Virgo
    DQ_ANALYSIS_STATE_VECTOR. If no DQ issues are found in active detectors,
    'DQOK' is labeled to GraceDb. Otherwise, 'DQV' is labeled. In all cases,
    the DQ states of all the state vectors checked are logged to GraceDb.

    This skips MDC events.

    Parameters
    ----------
    event : dict
        Details of event.
    graceid : str
        GraceID of event to which to log.
    start, end : int or float
        GPS start and end times desired.
    """
    # Skip MDC events.
    if event.get('search') == 'MDC':
        log.info('Skipping state vector checks because %s is an MDC',
                 event['graceid'])
        return event

    # Create caches for all detectors
    instruments = event['instruments'].split(',')
    pipeline = event['pipeline']
    pre, post = app.conf['check_vector_prepost'][pipeline]
    start, end = start - pre, end + post
    prepost_msg = "Check looked within -{}/+{} seconds of superevent. ".format(
        pre, post)

    ifos = {key.split(':')[0] for key, val in
            app.conf['llhoft_channels'].items()}
    caches = {ifo: create_cache(ifo, start, end) for ifo in ifos}

    # Examine injection and DQ states
    # Do not analyze DMT-DQ_VECTOR if pipeline uses gated h(t)
    states = {}
    analysis_channels = app.conf['llhoft_channels'].items()
    if app.conf['uses_gatedhoft'][pipeline]:
        analysis_channels = {k: v for k, v in analysis_channels
                             if k[3:] != 'DMT-DQ_VECTOR'}.items()
    for channel, bits in analysis_channels:
        states.update(check_vector(caches[channel.split(':')[0]], channel,
                                   start, end, globals()[bits]))
        #  Hard coded not() of Virgo DQ_VETO_* streams
        states.update({key: not(value) for key, value in states.items()
                       if key[:10] == 'V1:DQ_VETO'})
    # Pick out DQ and injection states, then filter for active detectors
    dq_states = {key: value for key, value in states.items()
                 if key.split('_')[-1] != 'INJ'}
    inj_states = {key: value for key, value in states.items()
                  if key.split('_')[-1] == 'INJ'}
    active_dq_states = {key: value for key, value in dq_states.items()
                        if key.split(':')[0] in instruments}
    active_inj_states = {key: value for key, value in inj_states.items()
                         if key.split(':')[0] in instruments}

    # Check iDQ states
    idq_probs = dict(check_idq(caches[channel.split(':')[0]],
                               channel, start, end)
                     for channel in app.conf['idq_channels'])

    # Logging iDQ to GraceDb
    if None not in idq_probs.values():
        if max(idq_probs.values()) >= app.conf['idq_pglitch_thresh']:
            idq_msg = ("iDQ glitch probability is high: "
                       "maximum p(glitch) is {}. ").format(
                json.dumps(idq_probs)[1:-1])
            # If iDQ p(glitch) is high and pipeline enabled, apply DQV
            if app.conf['idq_veto'][pipeline]:
                gracedb.create_label('DQV', graceid)
        else:
            idq_msg = ("iDQ glitch probabilities at both H1 and L1 "
                       "are good (below {} threshold). "
                       "Maximum p(glitch) is {}. ").format(
                           app.conf['idq_pglitch_thresh'],
                           json.dumps(idq_probs)[1:-1])
    else:
        idq_msg = "iDQ glitch probabilities unknown. "
    gracedb.client.writeLog(graceid, idq_msg + prepost_msg,
                            tag_name=['data_quality'])

    # Labeling INJ to GraceDb
    if False in active_inj_states.values():
        # Label 'INJ' if injection found in active IFOs
        gracedb.create_label('INJ', graceid)
    if False in inj_states.values():
        # Write all found injections into GraceDb log
        injs = [k for k, v in inj_states.items() if v is False]
        inj_fmt = "Injection found.\n{}\n"
        inj_msg = inj_fmt.format(
            generate_table('Injection bits', [], injs, []))
    elif all(inj_states.values()) and len(inj_states.values()) > 0:
        inj_msg = 'No HW injections found. '
    else:
        inj_msg = 'Injection state unknown. '
    gracedb.client.writeLog(graceid, inj_msg + prepost_msg,
                            tag_name=['data_quality'])

    # Determining overall_dq_active_state
    if None in active_dq_states.values() or len(
            active_dq_states.values()) == 0:
        overall_dq_active_state = None
    elif False in active_dq_states.values():
        overall_dq_active_state = False
    elif all(active_dq_states.values()):
        overall_dq_active_state = True
    goods = [k for k, v in dq_states.items() if v is True]
    bads = [k for k, v in dq_states.items() if v is False]
    unknowns = [k for k, v in dq_states.items() if v is None]
    fmt = "Detector state for active instruments is {}.\n{}"
    msg = fmt.format(
        {None: 'unknown', False: 'bad', True: 'good'}[overall_dq_active_state],
        generate_table('Data quality bits', goods, bads, unknowns)
    )
    if app.conf['uses_gatedhoft'][pipeline]:
        gate_msg = ('Pipeline {} uses gated h(t),'
                    ' LIGO DMT-DQ_VECTOR not checked.').format(pipeline)
    else:
        gate_msg = ''

    # Labeling DQOK/DQV to GraceDb
    gracedb.client.writeLog(
        graceid, msg + prepost_msg + gate_msg, tag_name=['data_quality'])
    if overall_dq_active_state is True:
        state = "pass"
        gracedb.create_label('DQOK', graceid)
    elif overall_dq_active_state is False:
        state = "fail"
        gracedb.create_label('DQV', graceid)
    else:
        state = "unknown"

    # Create and upload DQR-compatible json
    state_summary = '{} {} {}'.format(inj_msg, idq_msg, msg)
    if state == "unknown":
        json_state = "error"
    else:
        json_state = state
    file = dqr_json(json_state, state_summary)
    filename = 'gwcelerydetcharcheckvectors-{}.json'.format(graceid)
    message = "DQR-compatible json generated from check_vectors results"
    gracedb.upload(
        json.dumps(file), filename, graceid, message)

    return event
