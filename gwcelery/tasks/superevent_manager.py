"""Module containing the functionality for creation and management of
superevents.

    * There is serial processing of triggers from low latency
      pipelines.
    * Dedicated **superevent** queue for this purpose.
    * Primary logic to respond to low latency triggers contained
      in :meth:`superevent_handler` function.
"""
import json

from celery.utils.log import get_task_logger
from glue.segments import segmentlist

from ..celery import app
from . import gracedb, lvalert

log = get_task_logger(__name__)


@lvalert.handler('test_gstlal',
                 'cbc_gstlal_mdc',
                 shared=False,
                 queue='superevent')
def superevent_handler(text):
    """LVAlert handler for superevent manager.
    Recieves payload from test and production nodes and
    serially processes them to create/modify superevents
    """
    payload = json.loads(text)
    gid = payload['uid']
    alert_type = payload['alert_type']

    sid, preferred_flag, superevents = gracedb.get_superevent(gid)
    superevents = superevent_segment_list(superevents)

    d_t_start = app.conf['superevent_d_t_start']
    d_t_end = app.conf['superevent_d_t_end']

    # Condition 1/4
    if sid is None and alert_type == 'new':
        log.debug('Entered 1st if')
        event_segment = gracedb.Event(payload['object'].get('gpstime'),
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
            gracedb.set_preferred_event(superevent.superevent_id,
                                        superevent.preferred_event,
                                        event_segment.gid)
        # Create a new event if not in any time window
        else:
            gracedb.create_superevent(payload,
                                      d_t_start=d_t_start,
                                      d_t_end=d_t_end)

    # Condition 2/4
    elif sid is None and alert_type == 'update':
        # Probable case of a restart
        log.debug('2nd if: Possible restart scenario')
        log.warning('No superevent found for alert_type update for %s', gid)
        log.warning('Creating new superevent for %s', gid)
        # update alerts don't have gpstime, hence fetch from gracedb
        event_dict = gracedb.get_event(gid)
        # add gpstime to payload dict since update alert don't have gpstime
        payload['object']['gpstime'] = event_dict['gpstime']

        gracedb.create_superevent(payload,
                                  d_t_start=d_t_start,
                                  d_t_end=d_t_end)

    # Condition 3/4
    elif sid and alert_type == 'new':
        # ERROR SITUATION
        log.debug('3rd if: SID returned and new alert')
        log.critical('Superevent %s exists for alert_type new for %s',
                     sid, gid)

    # Condition 4/4
    elif sid and alert_type == 'update':
        # Logic to update the preferred G event
        log.debug('4th if: SID returned update alert. Change the pointer')
        superevent = list(filter(lambda s:
                                 s.superevent_id == sid, superevents))
        # superevent will contain only one item based on matching sid
        gracedb.set_preferred_event(superevent[0].superevent_id,
                                    superevent[0].preferred_event,
                                    gid)
    # Condition else
    else:
        log.critical('Unhandled by parse_trigger, passing...')


def superevent_segment_list(superevents):
    """Ingests a list of superevent dictionaries, creates
    :class:`gracedb.SuperEvent` objects from each and returns
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
        [gracedb.SuperEvent(s['t_0'], s['t_start'], s['t_end'],
                            s['superevent_id'], s['preferred_event'], s)
            for s in superevents]
    return segmentlist(superevent_list)
