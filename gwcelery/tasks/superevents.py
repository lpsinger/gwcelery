"""Module containing the functionality for creation and management of
superevents.

    * There is serial processing of triggers from low latency
      pipelines.
    * Dedicated **superevent** queue for this purpose.
    * Primary logic to respond to low latency triggers contained
      in :meth:`handle` function.
"""
from celery.utils.log import get_task_logger
from ligo.gracedb.exceptions import HTTPError
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
    alert_type = payload['alert_type']

    if alert_type != 'new':
        log.info('Not new type alert, passing...')
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

    event_info = _get_event_info(payload)

    if event_info['search'] == 'MDC':
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

    d_t_start, d_t_end = _get_dts(event_info)

    if sid is None:
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
                                      d_t_end,
                                      category)
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
        # FIXME handle the 400 properly when arises
        try:
            _update_superevent(superevent.superevent_id,
                               superevent.preferred_event,
                               event_info,
                               t_start=new_t_start,
                               t_end=new_t_end)
        except HTTPError as err:
            if err.status == 400 and err.reason == "Bad Request":
                log.exception("Server returned bad request")
            else:
                raise err

    else:
        log.critical('Superevent %s exists for alert_type new for %s',
                     sid, gid)


def _get_event_info(payload):
    """Helper function to fetch required event info (from GraceDb)
    at once and reduce polling
    """
    # pull basic info
    alert_type = payload.get('alert_type')
    payload = payload.get('object', payload)
    event_info = dict(
        graceid=payload['graceid'],
        gpstime=payload['gpstime'],
        far=payload['far'],
        instruments=payload['instruments'],
        group=payload['group'],
        pipeline=payload['pipeline'],
        search=payload.get('search'),
        alert_type=alert_type)
    # pull pipeline based extra attributes
    if payload['group'].lower() == 'cbc':
        event_info['snr'] = \
             payload['extra_attributes']['CoincInspiral']['snr']
    if payload['pipeline'].lower() == 'cwb':
        extra_attributes = ['duration', 'start_time', 'snr']
        event_info.update(
            {attr:
             payload['extra_attributes']['MultiBurst'][attr]
             for attr in extra_attributes})
    elif payload['pipeline'].lower() == 'olib':
        extra_attributes = ['quality_mean', 'frequency_mean']
        event_info.update(
            {attr:
             payload['extra_attributes']['LalInferenceBurst'][attr]
             for attr in extra_attributes})
        # oLIB snr key has a different name, call it snr
        event_info['snr'] = \
            payload[
                'extra_attributes']['LalInferenceBurst']['omicron_snr_network']
    return event_info


def _get_dts(event_info):
    """
    Returns the d_t_start and d_t_end values based on CBC/Burst
    type alerts
    """
    pipeline = event_info['pipeline'].lower()
    if pipeline == 'cwb':
        d_t_start = d_t_end = event_info['duration']
    elif pipeline == 'olib':
        d_t_start = d_t_end = (event_info['quality_mean'] /
                               event_info['frequency_mean'])
    else:
        d_t_start = app.conf['superevent_d_t_start'].get(
            pipeline, app.conf['superevent_default_d_t_start'])
        d_t_end = app.conf['superevent_d_t_end'].get(
            pipeline, app.conf['superevent_default_d_t_end'])
    return d_t_start, d_t_end


def _keyfunc(event_info):
    group = event_info['group'].lower()
    # FIXME Currently single IFOs are determined from the SingleInspiral
    # tables. Uncomment the line below to revert to normal behavior when fixed
    # num_ifos = len(event_info['instruments'].split(","))
    num_ifos = gracedb.get_number_of_instruments(event_info['graceid'])
    ifo_rank = (num_ifos <= 1)
    try:
        group_rank = ['cbc', 'burst'].index(group)
    except ValueError:
        group_rank = float('inf')
    # return the index of group and negative snr in spirit
    # of rank being lower for higher SNR for CBC
    if group == 'cbc':
        return ifo_rank, group_rank, -1.0*event_info['snr']
    else:
        return ifo_rank, group_rank, event_info['far']


def _update_superevent(superevent_id, preferred_event, new_event_dict,
                       t_start, t_end):
    """
    Update preferred event and/or change time window.
    Events with multiple detectors take precedence over
    single-detector events, then CBC events take precedence
    over burst events, and any remaining tie is broken by SNR/FAR
    values for CBC/Burst. Single detector are not promoted
    to preferred event status, if existing preferred event is
    multi-detector

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
    preferred_event_dict = _get_event_info(gracedb.get_event(preferred_event))

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
