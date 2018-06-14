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
                 'cbc_gstlal_mdc',
                 'test_gstlal',
                 'test_pycbc',
                 'test_mbtaonline',
                 'test_gstlal_mdc',
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
            'skipping %s because LVAlert message does not provide FAR', gid)
        return
    else:
        if far < app.conf['superevent_far_threshold']:
            log.info("Skipping processing of %s because of low far", gid)
            return

    sid, preferred_flag, superevents = gracedb.get_superevent(gid)
    superevents = _superevent_segment_list(superevents)

    d_t_start, d_t_end = _get_dts(payload)

    # Condition 1/2
    if sid is None and alert_type == 'new':
        log.debug('Entered 1st if')
        event_segment = _Event(payload['object'].get('gpstime'),
                               payload['uid'],
                               payload['object'].get('group'),
                               payload['object'].get('pipeline'),
                               payload['object'].get('search'),
                               event_dict=payload)

        # Check which superevent window trigger gpstime falls in
        if superevents.intersects_segment(event_segment):
            # FIXME .find() has to be generalized when event_segments
            # have a chance of not completely being contained in a
            # superevent segment
            superevent = superevents[superevents.find(event_segment)]
            log.info('Event %s in window of %s',
                     gid, superevent.superevent_id)
            gracedb.add_event_to_superevent(superevent.superevent_id,
                                            event_segment.gid)
            # ADDITIONAL LOGIC HERE IF THE TIME
            # WINDOW IS TO BE CHANGED BASED ON
            # TRIGGER PARAMETERS
            _update_preferred_event(superevent.superevent_id,
                                    superevent.preferred_event,
                                    event_segment.gid)
        # Create a new event if not in any time window
        else:
            gracedb.create_superevent(payload,
                                      d_t_start=d_t_start,
                                      d_t_end=d_t_end)

    # Condition 2/2
    elif sid and alert_type == 'new':
        # ERROR SITUATION
        log.debug('3rd if: SID returned and new alert')
        log.critical('Superevent %s exists for alert_type new for %s',
                     sid, gid)
    # Condition else
    else:
        log.critical('Unhandled by parse_trigger, passing...')


# FIXME: Unify _get_dts and _far_check, call get_event only once
def _get_dts(payload):
    """
    Returns the dt_start and dt_end values based on CBC/Burst
    for new and update type alerts
    """
    alert_type = payload['alert_type']
    if alert_type == 'new':
        group = payload['object']['group'].lower()
    else:
        group = gracedb.get_event(payload['uid'])['group'].lower()

    dt_start = app.conf['superevent_d_t_start'].get(
        group, app.conf['superevent_default_d_t_start'])

    dt_end = app.conf['superevent_d_t_end'].get(
        group, app.conf['superevent_default_d_t_end'])

    return dt_start, dt_end


def _update_preferred_event(sid, preferred_event, gid):
    """
    Update superevent with the new trigger id based on FAR values.

    Parameters
    ----------
    sid : str
        superevent uid
    preferred_event : str
        preferred event id of the superevent
    gid : str
        uid of the new trigger
    """
    new_event = gracedb.client.event(gid).json()
    preferred_event = gracedb.client.event(preferred_event).json()
    if new_event['far'] < preferred_event['far']:
        gracedb.set_preferred_event(sid, gid)


def _superevent_segment_list(superevents):
    """Ingests a list of superevent dictionaries, and returns
    a segmentlist of the same

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
    superevent_list = \
        [_SuperEvent(s['t_0'], s['t_start'], s['t_end'],
                     s['superevent_id'], s['preferred_event'], s)
            for s in superevents]
    return segmentlist(superevent_list)


class _Event(segment):
    """An event implemented as an extension of
    :class:`glue.segments.segment`
    """
    def __new__(cls, t0, *args, **kwargs):
        return super().__new__(cls, t0, t0)

    def __init__(self, t0, gid, group=None, pipeline=None,
                 search=None, event_dict={}):
        self.t0 = t0
        self.gid = gid
        self.group = group
        self.pipeline = pipeline
        self.search = search
        self.event_dict = event_dict


class _SuperEvent(segment):
    """An superevent implemented as an extension of
    :class:`glue.segments.segment`
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
