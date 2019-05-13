"""Module containing the functionality for creation and management of
superevents.

*   There is serial processing of triggers from low latency pipelines.
*   Dedicated **superevent** queue for this purpose.
*   Primary logic to respond to low latency triggers contained in
    :meth:`handle` function.
"""
from celery.utils.log import get_task_logger
from ligo.segments import segment, segmentlist

from ..import app
from . import gracedb, lvalert

log = get_task_logger(__name__)


@lvalert.handler('cbc_gstlal',
                 'cbc_spiir',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 'burst_olib',
                 'burst_cwb',
                 queue='superevent',
                 shared=False)
def handle(payload):
    """LVAlert handler for superevent manager.

    Receives payload from test and production nodes and serially processes them
    to create/modify superevents."""
    if payload['alert_type'] != 'new':
        return

    gid = payload['uid']

    try:
        far = payload['object']['far']
    except KeyError:
        log.info(
            'Skipping %s because LVAlert message does not provide FAR', gid)
        return
    else:
        if far > app.conf['superevent_far_threshold']:
            log.info("Skipping processing of %s because of low FAR", gid)
            return

    event_info = payload['object']

    if event_info.get('search') == 'MDC':
        category = 'mdc'
    elif event_info['group'] == 'Test':
        category = 'test'
    else:
        category = 'production'

    superevents = gracedb.get_superevents('category: {} {} .. {}'.format(
        category,
        event_info['gpstime'] - app.conf['superevent_query_d_t_start'],
        event_info['gpstime'] + app.conf['superevent_query_d_t_end']))

    for superevent in superevents:
        if gid in superevent['gw_events']:
            sid = superevent['superevent_id']
            break  # Found matching superevent
    else:
        sid = None  # No matching superevent

    t_start, t_end = get_ts(event_info)

    if sid is None:
        log.debug('Entered 1st if')
        event_segment = _Event(event_info['gpstime'],
                               t_start, t_end,
                               event_info['graceid'],
                               event_info['group'],
                               event_info['pipeline'],
                               event_info.get('search'),
                               event_dict=event_info)

        superevent = _partially_intersects(superevents, event_segment)

        if not superevent:
            log.info('New event %s with no superevent in GraceDB, '
                     'creating new superevent', gid)
            gracedb.create_superevent(event_info['graceid'],
                                      event_info['gpstime'],
                                      t_start, t_end, category)
            return

        log.info('Event %s in window of %s. Adding event to superevent',
                 gid, superevent.superevent_id)
        gracedb.add_event_to_superevent(superevent.superevent_id,
                                        event_segment.gid)
        # extend the time window of the superevent
        new_superevent = superevent | event_segment
        if new_superevent != superevent:
            log.info("%s not completely contained in %s, "
                     "extending superevent window",
                     event_segment.gid, superevent.superevent_id)
            new_t_start, new_t_end = new_superevent[0], new_superevent[1]

        else:
            log.info("%s is completely contained in %s",
                     event_segment.gid, superevent.superevent_id)
            new_t_start = new_t_end = None
        _update_superevent(superevent.superevent_id,
                           superevent.preferred_event,
                           event_info,
                           t_start=new_t_start,
                           t_end=new_t_end)
    else:
        log.critical('Superevent %s exists for alert_type new for %s',
                     sid, gid)


def get_ts(event):
    """Get time extent of an event, depending on pipeline-specific parameters.

    *   For CWB, use the event's ``duration`` field.
    *   For oLIB, use the ratio of the event's ``quality_mean`` and
        ``frequency_mean`` fields.
    *   For all other pipelines, use the
        :obj:`~gwcelery.conf.superevent_d_t_start` and
        :obj:`~gwcelery.conf.superevent_d_t_start` configuration values.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    t_start : float
        Segment start time in GPS seconds.

    t_end : float
        Segment end time in GPS seconds.
    """
    pipeline = event['pipeline'].lower()
    if pipeline == 'cwb':
        attribs = event['extra_attributes']['MultiBurst']
        d_t_start = d_t_end = attribs['duration']
    elif pipeline == 'olib':
        attribs = event['extra_attributes']['LalInferenceBurst']
        d_t_start = d_t_end = (attribs['quality_mean'] /
                               attribs['frequency_mean'])
    else:
        d_t_start = app.conf['superevent_d_t_start'].get(
            pipeline, app.conf['superevent_default_d_t_start'])
        d_t_end = app.conf['superevent_d_t_end'].get(
            pipeline, app.conf['superevent_default_d_t_end'])
    return event['gpstime'] - d_t_start, event['gpstime'] + d_t_end


def get_snr(event):
    """Get the SNR from the LVAlert packet.

    Different groups and pipelines store the SNR in different fields.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    snr : float
        The SNR.
    """
    group = event['group'].lower()
    pipeline = event['pipeline'].lower()
    if group == 'cbc':
        attribs = event['extra_attributes']['CoincInspiral']
        return attribs['snr']
    elif pipeline == 'cwb':
        attribs = event['extra_attributes']['MultiBurst']
        return attribs['snr']
    elif pipeline == 'olib':
        attribs = event['extra_attributes']['LalInferenceBurst']
        return attribs['omicron_snr_network']
    else:
        raise NotImplementedError('SNR attribute not found')


def get_instruments(event):
    """Get the participating instruments from the LVAlert packet.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    set
        The set of instruments that contributed to the ranking statistic for
        the event.

    Notes
    -----
    The number of instruments that contributed *data* to an event is given by
    the ``instruments`` key of the GraceDB event JSON structure. However, some
    pipelines (e.g. gstlal) have a distinction between which instruments
    contributed *data* and which were considered in the *ranking* of the
    candidate. For such pipelines, we infer which pipelines contributed to the
    ranking by counting only the SingleInspiral records for which the chi
    squared field is non-empty.
    """
    try:
        attribs = event['extra_attributes']['SingleInspiral']
        ifos = {single['ifo'] for single in attribs
                if single.get('chisq') is not None}
    except KeyError:
        ifos = set(event['instruments'].split(','))
    return ifos


def should_publish(event):
    """Determine whether an event should be published as a public alert.

    All of the following conditions must be true for a public alert:

    *   The event's ``offline`` flag is not set.
    *   The event's significance was estimated using data from 2 or more
        gravitational-wave detectors.
    *   The event's false alarm rate, weighted by the group-specific trials
        factor as specified by the
        :obj:`~gwcelery.conf.preliminary_alert_trials_factor` configuration
        setting, is less than or equal to
        :obj:`~gwcelery.conf.preliminary_alert_far_threshold`.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    should_publish : bool
        :obj:`True` if the event meets the criteria for a public alert or
        :obj:`False` if it does not.
    """
    group = event['group'].lower()
    trials_factor = app.conf['preliminary_alert_trials_factor'][group]
    far_threshold = app.conf['preliminary_alert_far_threshold'][group]
    far = trials_factor * event['far']
    ifos = get_instruments(event)
    num_ifos = len(ifos)
    return not event['offline'] and num_ifos > 1 and far <= far_threshold


def keyfunc(event):
    """Key function for selection of the preferred event.

    Return a value suitable for identifying the preferred event. Given events
    ``a`` and ``b``, ``a`` is preferred over ``b`` if
    ``keyfunc(a) < keyfunc(b)``, else ``b`` is preferred.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    key : tuple
        The comparison key.

    Notes
    -----
    Tuples are compared lexicographically in Python: they are compared
    element-wise until an unequal pair of elements is found.
    """
    group = event['group'].lower()
    try:
        group_rank = ['cbc', 'burst'].index(group)
    except ValueError:
        group_rank = float('inf')
    tie_breaker = -get_snr(event) if group == 'cbc' else event['far']
    return not should_publish(event), group_rank, tie_breaker


def _update_superevent(superevent_id, preferred_event, new_event_dict,
                       t_start, t_end):
    """
    Update preferred event and/or change time window. Events with multiple
    detectors take precedence over single-detector events, then CBC events take
    precedence over burst events, and any remaining tie is broken by SNR/FAR
    values for CBC/Burst. Single detector are not promoted to preferred event
    status, if existing preferred event is multi-detector

    Parameters
    ----------
    superevent_id : str
        superevent uid
    preferred_event : str
        preferred event id of the superevent
    new_event_dict : dict
        event info of the new trigger as a dictionary
    t_start : float
        start time of `superevent_id`, None for no change
    t_end : float
        end time of `superevent_id`, None for no change
    """
    preferred_event_dict = gracedb.get_event(preferred_event)

    kwargs = {}
    if t_start is not None:
        kwargs['t_start'] = t_start
    if t_end is not None:
        kwargs['t_end'] = t_end
    if keyfunc(new_event_dict) < keyfunc(preferred_event_dict):
        kwargs['preferred_event'] = new_event_dict['graceid']

    if kwargs:
        gracedb.update_superevent(superevent_id, **kwargs)


def _superevent_segment_list(superevents):
    """Ingests a list of superevent dictionaries, and returns a segmentlist
    with start and end times as the duration of each segment.

    Parameters
    ----------
    superevents : list
        List of superevent dictionaries (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_superevents`).

    Returns
    -------
    superevent_list : segmentlist
        superevents as a segmentlist object
    """
    return segmentlist([_SuperEvent(s.get('t_start'),
                        s.get('t_end'),
                        s.get('t_0'),
                        s.get('superevent_id'),
                        s.get('preferred_event'),
                        s)
                       for s in superevents])


def _partially_intersects(superevents, event_segment):
    """Similar to :meth:`segmentlist.find` except it also returns the segment
    of `superevents` which partially intersects argument. If there are more
    than one intersections, first occurence is returned.

    Parameters
    ----------
    superevents : list
        list pulled down using the gracedb client
        :method:`superevents`
    event_segment : segment
        segment object whose index is wanted

    Returns
    -------
    match_segment   : segment
        segment in `self` which intersects. `None` if not found
    """
    # create a segmentlist using start and end times
    superevents = _superevent_segment_list(superevents)
    for s in superevents:
        if s.intersects(event_segment):
            return s
    return None


class _Event(segment):
    """An event implemented as an extension of :class:`segment`."""
    def __new__(cls, t0, t_start, t_end, *args, **kwargs):
        return super().__new__(cls, t_start, t_end)

    def __init__(self, t0, t_start, t_end, gid, group=None, pipeline=None,
                 search=None, event_dict={}):
        self.t0 = t0
        self.gid = gid
        self.group = group
        self.pipeline = pipeline
        self.search = search
        self.event_dict = event_dict


class _SuperEvent(segment):
    """An superevent implemented as an extension of :class:`segment`."""
    def __new__(cls, t_start, t_end, *args, **kwargs):
        return super().__new__(cls, t_start, t_end)

    def __init__(self, t_start, t_end, t_0, sid,
                 preferred_event=None, event_dict={}):
        self.t_start = t_start
        self.t_end = t_end
        self.t_0 = t_0
        self.superevent_id = sid
        self.preferred_event = preferred_event
        self.event_dict = event_dict
