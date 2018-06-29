"""Module containing the functionality for creation and management of
superevents.

    * There is serial processing of triggers from low latency
      pipelines.
    * Dedicated **superevent** queue for this purpose.
    * Primary logic to respond to low latency triggers contained
      in :meth:`handle` function.
"""
from celery.utils.log import get_task_logger
from glue.segments import segment, segmentlist

from ..celery import app
from . import gracedb, lvalert

log = get_task_logger(__name__)


@lvalert.handler('cbc_gstlal',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 'burst_lib',
                 'burst_cwb',
                 'test_gstlal',
                 'test_pycbc',
                 'test_mbtaonline',
                 queue='superevent',
                 shared=False)
def handle(payload):
    """LVAlert handler for superevent manager.
    Recieves payload from test and production nodes and
    serially processes them to create/modify superevents
    """
    gid = payload['uid']
    alert_type = payload['alert_type']

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

    event_info = _get_event_info(payload)

    query_times = (event_info['gpstime'] -
                   app.conf['superevent_query_d_t_start'],
                   event_info['gpstime'] +
                   app.conf['superevent_query_d_t_end'])

    sid, preferred_flag, superevents = gracedb.get_superevents(
        gid, query='''{} .. {}'''.format(*query_times))

    d_t_start, d_t_end = _get_dts(event_info)

    # Condition 1/2
    if sid is None and alert_type == 'new':
        log.debug('Entered 1st if')
        event_segment = _Event(event_info['gpstime'],
                               event_info['gpstime'] - d_t_start,
                               event_info['gpstime'] + d_t_end,
                               event_info['graceid'],
                               event_info['group'],
                               event_info['pipeline'],
                               event_info['search'],
                               event_dict=payload)

        superevent = _partially_intersects(superevents, event_segment)

        if not superevent:
            log.info('New event %s with no superevent in GraceDb, '
                     'creating new superevent', gid)
            gracedb.create_superevent(event_info['graceid'],
                                      event_info['gpstime'],
                                      d_t_start,
                                      d_t_end)
            return

        log.info('Event %s in window of %s. Adding event to superevent',
                 gid, superevent.superevent_id)
        gracedb.add_event_to_superevent(superevent.superevent_id,
                                        event_segment.gid)
        # extend the time window of the superevent
        new_superevent = superevent | event_segment
        if new_superevent is not superevent:
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

    elif sid and alert_type == 'new':
        # ERROR SITUATION
        log.debug('3rd if: SID returned and new alert')
        log.critical('Superevent %s exists for alert_type new for %s',
                     sid, gid)
    # Condition else
    else:
        log.critical('Unhandled by parse_trigger, passing...')


def _get_event_info(payload):
    """Helper function to fetch required event info (from GraceDb)
    at once and reduce polling
    """
    # pull basic info
    event_info = dict(
        graceid=payload['object']['graceid'],
        gpstime=payload['object']['gpstime'],
        far=payload['object']['far'],
        group=payload['object']['group'],
        pipeline=payload['object']['pipeline'],
        search=payload['object'].get('search'),
        alert_type=payload['alert_type'])
    # pull pipeline based extra attributes
    if payload['object']['pipeline'].lower() == 'cwb':
        extra_attributes = ['duration', 'start_time']
        event_info.update(
            {attr:
             payload['object']['extra_attributes']['MultiBurst'][attr]
             for attr in extra_attributes})
    elif payload['object']['pipeline'].lower() == 'lib':
        extra_attributes = ['quality_mean', 'frequency_mean']
        event_info.update(
            {attr:
             payload['object']['extra_attributes']['LalInferenceBurst'][attr]
             for attr in extra_attributes})
    # if required, add CBC specific extra_attributes here
    return event_info


def _get_dts(event_info):
    """
    Returns the d_t_start and d_t_end values based on CBC/Burst
    type alerts
    """
    group = event_info['group']
    pipeline = event_info['pipeline']
    if pipeline.lower() == 'cwb':
        d_t_start = d_t_end = event_info['duration']
    elif pipeline.lower() == 'lib':
        d_t_start = d_t_end \
            = event_info['quality_mean']/event_info['frequency_mean']
    elif group.lower() == 'cbc':
        d_t_start = app.conf['superevent_d_t_start'][pipeline.lower()]
        d_t_end = app.conf['superevent_d_t_end'][pipeline.lower()]
    else:
        d_t_start = app.conf['superevent_default_d_t_start']
        d_t_end = app.conf['superevent_default_d_t_end']
    return d_t_start, d_t_end


def _keyfunc(event):
    group = event['group'].lower()
    try:
        group_rank = ['cbc', 'burst'].index(group)
    except ValueError:
        group_rank = float('inf')
    return group_rank, event['far']


def _update_superevent(superevent_id, preferred_event, new_event_dict,
                       t_start, t_end):
    """
    Update preferred event and/or change time window.
    Decision between `preferred_event` and `new_event`
    based on FAR values if groups match, else CBC takes
    precedence over burst

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
    preferred_event_dict = gracedb.client.event(preferred_event).json()

    kwargs = {}
    if t_start is not None:
        kwargs['t_start'] = t_start
    if t_end is not None:
        kwargs['t_end'] = t_end
    if _keyfunc(new_event_dict) < _keyfunc(preferred_event_dict):
        kwargs['preferred_event'] = new_event_dict['graceid']

    if kwargs:
        gracedb.update_superevent(superevent_id, **kwargs)


def _superevent_segment_list(superevents):
    """Ingests a list of superevent dictionaries, and returns
    a segmentlist with start and end times as the duration of
    each segment

    Parameters
    ----------
    superevents : list
        list of superevent dictionaries, usually fetched by
        :meth:`GraceDb.superevents()`.

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
    """Similar to :meth:`segmentlist.find`
    except it also returns the segment of
    `superevents` which partially intersects argument.
    If there are more than one intersections,
    first occurence is returned.

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
    """An event implemented as an extension of
    :class:`segment`
    """
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
    """An superevent implemented as an extension of
    :class:`segment`
    """
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
