"""Module containing the functionality for creation and management of
superevents.

*   There is serial processing of triggers from low latency pipelines.
*   Dedicated **superevent** queue for this purpose.
*   Primary logic to respond to low latency triggers contained in
    :meth:`process` function.
"""
from itertools import filterfalse

from celery.utils.log import get_task_logger
from ligo.segments import segment, segmentlist

from ..import app
from . import gracedb, igwn_alert

log = get_task_logger(__name__)

REQUIRED_LABELS_BY_GROUP = {
    'cbc': {'PASTRO_READY', 'EMBRIGHT_READY', 'SKYMAP_READY'},
    'burst': {'SKYMAP_READY'}
}
"""These labels should be present on an event to consider it to
be complete.
"""

FROZEN_LABEL = 'EM_Selected'
"""This label indicates that the superevent manager should make no further
changes to the preferred event."""

READY_LABEL = 'EM_READY'
"""This label indicates that a preferred event has been assigned and it
has all data products required to make it ready for annotations."""


@igwn_alert.handler('cbc_gstlal',
                    'cbc_spiir',
                    'cbc_pycbc',
                    'cbc_mbta',
                    'burst_olib',
                    'burst_cwb',
                    shared=False)
def handle(payload):
    """Respond to IGWN alert topics from low-latency search pipelines and
    delegate to :meth:`process` for superevent management.
    """
    alert_type = payload['alert_type']
    gid = payload['object']['graceid']

    try:
        far = payload['object']['far']
    except KeyError:
        log.info('Skipping %s because it lacks a FAR', gid)
        return

    if far > app.conf['superevent_far_threshold']:
        log.info("Skipping processing of %s because of high FAR", gid)
        return

    priority = 1
    if alert_type == 'label_added':
        priority = 0
        label = payload['data']['name']
        group = payload['object']['group'].lower()
        if label == 'RAVEN_ALERT':
            log.info('Label %s added to %s', label, gid)
        elif label not in REQUIRED_LABELS_BY_GROUP[group]:
            return
        elif not is_complete(payload['object']):
            log.info("Ignoring since %s has %s labels. "
                     "It is not complete", gid, payload['object']['labels'])
            return
    elif alert_type != 'new':
        return

    process.si(payload).apply_async(priority=priority)


@gracedb.task(queue='superevent', shared=False)
@gracedb.catch_retryable_http_errors
def process(payload):
    """
    Respond to `payload` and serially processes them to create new superevents,
    add events to existing ones.

    Parameters
    ----------
    payload : dict
        IGWN alert payload

    """
    event_info = payload['object']
    gid = event_info['graceid']
    category = get_category(event_info)
    t_0, t_start, t_end = get_ts(event_info)

    if event_info.get('superevent'):
        sid = event_info['superevent']
        log.info('Event %s already belongs to superevent %s', gid, sid)
        # superevent_neighbours has current and nearby superevents
        s = event_info['superevent_neighbours'][sid]
        superevent = _SuperEvent(s['t_start'],
                                 s['t_end'],
                                 s['t_0'],
                                 s['superevent_id'])
        _update_superevent(superevent.superevent_id,
                           event_info,
                           t_0=t_0,
                           t_start=None,
                           t_end=None)
    else:
        log.info('Event %s does not yet belong to a superevent', gid)
        superevents = gracedb.get_superevents('category: {} {} .. {}'.format(
            category,
            event_info['gpstime'] - app.conf['superevent_query_d_t_start'],
            event_info['gpstime'] + app.conf['superevent_query_d_t_end']))
        for s in superevents:
            if gid in s['gw_events']:
                sid = s['superevent_id']
                log.info('Event %s found assigned to superevent %s', gid, sid)
                if payload['alert_type'] == 'label_added':
                    log.info('Label %s added to %s',
                             payload['data']['name'], gid)
                elif payload['alert_type'] == 'new':
                    log.info('new alert type for %s with '
                             'existing superevent %s. '
                             'No action required', gid, sid)
                    return
                superevent = _SuperEvent(s['t_start'],
                                         s['t_end'],
                                         s['t_0'],
                                         s['superevent_id'])
                _update_superevent(superevent.superevent_id,
                                   event_info,
                                   t_0=t_0,
                                   t_start=None,
                                   t_end=None)
                break
        else:  # s not in superevents
            event_segment = _Event(t_start, t_end, t_0, event_info['graceid'])

            superevent = _partially_intersects(superevents,
                                               event_segment)

            if superevent:
                sid = superevent.superevent_id
                log.info('Event %s in window of %s. '
                         'Adding event to superevent', gid, sid)
                gracedb.add_event_to_superevent(sid, event_segment.gid)
                # extend the time window of the superevent
                new_superevent = superevent | event_segment
                if new_superevent != superevent:
                    log.info('%s not completely contained in %s, '
                             'extending superevent window',
                             event_segment.gid, sid)
                    new_t_start, new_t_end = new_superevent

                else:  # new_superevent == superevent
                    log.info('%s is completely contained in %s',
                             event_segment.gid, sid)
                    new_t_start = new_t_end = None
                _update_superevent(superevent.superevent_id,
                                   event_info,
                                   t_0=t_0,
                                   t_start=new_t_start,
                                   t_end=new_t_end)
            else:  # not superevent
                log.info('New event %s with no superevent in GraceDB, '
                         'creating new superevent', gid)
                sid = gracedb.create_superevent(event_info['graceid'],
                                                t_0, t_start, t_end)

    if should_publish(event_info):
        gracedb.create_label.delay('ADVREQ', sid)
        if is_complete(event_info):
            if app.conf['preliminary_alert_timeout'] \
                    and 'EARLY_WARNING' not in event_info['labels']:
                gracedb.create_label.s(FROZEN_LABEL, sid).set(
                    queue='superevent',
                    countdown=app.conf['preliminary_alert_timeout']
                ).delay()
            else:  # fast path if no countdown
                gracedb.create_label(FROZEN_LABEL, sid)


def get_category(event):
    """Get the superevent category for an event.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`).

    Returns
    -------
    {'mdc', 'test', 'production'}

    """
    if event.get('search') == 'MDC':
        return 'mdc'
    elif event['group'] == 'Test':
        return 'test'
    else:
        return 'production'


def get_ts(event):
    """Get time extent of an event, depending on pipeline-specific parameters.

    *   For CWB, use the event's ``duration`` field.
    *   For oLIB, use the ratio of the event's ``quality_mean`` and
        ``frequency_mean`` fields.
    *   For all other pipelines, use the
        :obj:`~gwcelery.conf.superevent_d_t_start` and
        :obj:`~gwcelery.conf.superevent_d_t_end` configuration values.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event` or
        ``preferred_event_data`` in igwn-alert packet.)

    Returns
    -------
    t_0: float
        Segment center time in GPS seconds.
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
    return (event['gpstime'], event['gpstime'] - d_t_start,
            event['gpstime'] + d_t_end)


def get_snr(event):
    """Get the SNR from the LVAlert packet.

    Different groups and pipelines store the SNR in different fields.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`, or
        ``preferred_event_data`` in igwn-alert packet.)

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
    """Get the instruments that contributed data to an event.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`, or
        ``preferred_event_data`` in igwn-alert packet.)

    Returns
    -------
    set
        The set of instruments that contributed to the event.

    """
    attribs = event['extra_attributes']['SingleInspiral']
    ifos = {single['ifo'] for single in attribs}
    return ifos


def get_instruments_in_ranking_statistic(event):
    """Get the instruments that contribute to the false alarm rate.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`, or
        ``preferred_event_data`` in igwn-alert packet.)

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

    For PyCBC Live in the O3 configuration, an empty chi^2 field does not mean
    that the detector did not contribute to the ranking; in fact, *all*
    detectors listed in the SingleInspiral table contribute to the significance
    even if the chi^2 is not computed for some of them. Hence PyCBC Live is
    handled as a special case.

    """
    if event['pipeline'].lower() == 'pycbc':
        return set(event['instruments'].split(','))
    else:
        attribs = event['extra_attributes']['SingleInspiral']
        return {single['ifo'] for single in attribs
                if single.get('chisq') is not None}


@app.task(shared=False)
def select_preferred_event(events):
    """Select the preferred event out of a list of G events, typically
    contents of a superevent, based on :meth:`keyfunc`.

    Parameters
    ----------
    events : list
        list of event dictionaries

    """
    # FIXME: Requires robust determination of an External event
    g_events = list(
        filterfalse(lambda x: x['graceid'].startswith('E'), events))
    return max(g_events, key=keyfunc)


def is_complete(event):
    """
    Determine if a G event is complete in the sense of the event
    has its data products complete i.e. has PASTRO_READY, SKYMAP_READY,
    EMBRIGHT_READY for CBC events and the SKYMAP_READY label for the
    Burst events. Test events are not processed by low-latency infrastructure
    and are always labeled complete.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`, or
        ``preferred_event_data`` in igwn-alert packet.)

    """
    group = event['group'].lower()
    label_set = set(event['labels'])
    required_labels = REQUIRED_LABELS_BY_GROUP[group]
    return required_labels.issubset(label_set)


def should_publish(event):
    """Determine whether an event should be published as a public alert.

    All of the following conditions must be true for a public alert:

    *   The event's ``offline`` flag is not set.
    *   The event's false alarm rate, weighted by the group-specific trials
        factor as specified by the
        :obj:`~gwcelery.conf.preliminary_alert_trials_factor` configuration
        setting, is less than or equal to
        :obj:`~gwcelery.conf.preliminary_alert_far_threshold`.

    Parameters
    ----------
    event : dict
        Event dictionary (e.g., the return value from
        :meth:`gwcelery.tasks.gracedb.get_event`, or
        ``preferred_event_data`` in igwn-alert packet.)

    Returns
    -------
    should_publish : bool
        :obj:`True` if the event meets the criteria for a public alert or
        :obj:`False` if it does not.

    """
    return all(_should_publish(event))


def _should_publish(event):
    """Wrapper around :meth:`should_publish`. Returns the boolean returns of
    the publishability criteria as a tuple for later use.
    """
    group = event['group'].lower()
    if 'EARLY_WARNING' in event['labels']:
        far_threshold = app.conf['early_warning_alert_far_threshold']
        trials_factor = app.conf['early_warning_alert_trials_factor']
    else:
        far_threshold = app.conf['preliminary_alert_far_threshold'][group]
        trials_factor = app.conf['preliminary_alert_trials_factor'][group]
    far = trials_factor * event['far']
    raven_coincidence = ('RAVEN_ALERT' in event['labels'])

    return (not event['offline'] and 'INJ' not in event['labels'],
            far <= far_threshold or raven_coincidence)


def keyfunc(event):
    """Key function for selection of the preferred event.

    Return a value suitable for identifying the preferred event. Given events
    ``a`` and ``b``, ``a`` is preferred over ``b`` if
    ``keyfunc(a) > keyfunc(b)``, else ``b`` is preferred.

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
        group_rank = ['burst', 'cbc'].index(group)
    except ValueError:
        group_rank = -1

    if group == 'cbc':
        group_rank = 1
        n_ifos = len(get_instruments(event))
        significance = get_snr(event)
    else:
        # We don't care about the number of detectors for burst events.
        n_ifos = -1
        # Smaller FAR -> higher IFAR -> more significant.
        # Use -FAR instead of IFAR=1/FAR so that rank for FAR=0 is defined.
        significance = -event['far']

    return (is_complete(event), *_should_publish(event), group_rank, n_ifos,
            significance)


def _update_superevent(superevent_id, new_event_dict,
                       t_0, t_start, t_end):
    """Update preferred event and/or change time window. Events with multiple
    detectors take precedence over single-detector events, then CBC events take
    precedence over burst events, and any remaining tie is broken by SNR/FAR
    values for CBC/Burst. Single detector are not promoted to preferred event
    status, if existing preferred event is multi-detector

    Parameters
    ----------
    superevent_id : str
        the superevent_id
    new_event_dict : dict
        event info of the new trigger as a dictionary
    t_0 : float
        center time of `superevent_id`, None for no change
    t_start : float
        start time of `superevent_id`, None for no change
    t_end : float
        end time of `superevent_id`, None for no change

    """
    # labels and preferred event in the IGWN alert are not the latest
    superevent_dict = gracedb.get_superevent(superevent_id)

    superevent_labels = superevent_dict['labels']
    preferred_event_dict = superevent_dict['preferred_event_data']
    kwargs = {}
    if t_start is not None:
        kwargs['t_start'] = t_start
    if t_end is not None:
        kwargs['t_end'] = t_end
    if FROZEN_LABEL not in superevent_labels:
        if keyfunc(new_event_dict) > keyfunc(preferred_event_dict):
            # update preferred event when EM_Selected is not applied
            kwargs['t_0'] = t_0
            kwargs['preferred_event'] = new_event_dict['graceid']

    if kwargs:
        gracedb.update_superevent(superevent_id, **kwargs)

    # completeness takes first precedence in deciding preferred event
    # necessary and suffiecient condition to superevent as ready
    if is_complete(new_event_dict):
        gracedb.create_label.delay(READY_LABEL, superevent_id)


def _superevent_segment_list(superevents):
    """Ingests a list of superevent dictionaries, and returns a segmentlist
    with start and end times as the duration of each segment.

    Parameters
    ----------
    superevents : list
        List of superevent dictionaries (e.g., the values
        of field ``superevent_neighbours`` in igwn-alert packet).

    Returns
    -------
    superevent_list : segmentlist
        superevents as a segmentlist object

    """
    return segmentlist(
        [_SuperEvent(s['t_start'], s['t_end'], s['t_0'], s['superevent_id'])
         for s in superevents])


def _partially_intersects(superevents, event_segment):
    """Similar to :meth:`segmentlist.find` except it also returns the segment
    of `superevents` which partially intersects argument. If there are more
    than one intersections, first occurence is returned.

    Parameters
    ----------
    superevents : list
        list of superevents. Typical value of
        ``superevent_neighbours.values()``.
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

    def __new__(cls, t_start, t_end, *args, **kwargs):
        return super().__new__(cls, t_start, t_end)

    def __init__(self, t_start, t_end, t_0, gid):
        self.t_0 = t_0
        self.gid = gid


class _SuperEvent(segment):
    """An superevent implemented as an extension of :class:`segment`."""

    def __new__(cls, t_start, t_end, *args, **kwargs):
        return super().__new__(cls, t_start, t_end)

    def __init__(self, t_start, t_end, t_0, sid):
        self.t_start = t_start
        self.t_end = t_end
        self.t_0 = t_0
        self.superevent_id = sid
