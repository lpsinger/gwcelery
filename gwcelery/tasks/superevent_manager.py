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

from ..celery import app
from . import gracedb, lvalert

log = get_task_logger(__name__)


@lvalert.handler('test_gstlal', 'cbc_gstlal_mdc', queue='superevent')
def superevent_handler(text):
    """LVAlert handler for superevent manager.
    Recieves payload from test and production nodes and
    serially processes them to create/modify superevents
    """
    payload = json.loads(text)

    gid = payload['uid']
    alert_type = payload['alert_type']
    gpstime = payload['object'].get('gpstime')
    # s_event_dict['superevents'] is the list of superevents,
    # sid is True if gid exists in any superevent gw_list
    sid, preferred_flag, s_event_dict = gracedb.get_superevent(gid)
    # FIXME as config grows, this could go into separate function
    d_t_start = app.conf['superevent_d_t_start']
    d_t_end = app.conf['superevent_d_t_end']
    # Condition 1/4
    if sid is None and alert_type == 'new':
        log.debug('Entered 1st if')
        # Check which superevent window trigger gpstime falls in
        for superevent in s_event_dict['superevents']:
            if superevent['t_start'] <= gpstime < superevent['t_end']:
                log.info('Event %s in window of %s',
                         gid, superevent['superevent_id'])
                gracedb.add_event_to_superevent(superevent['superevent_id'],
                                                gid)
                # ADDITIONAL LOGIC HERE IF THE TIME
                # WINDOW IS TO BE CHANGED BASED ON
                # TRIGGER PARAMETERS
                # gracedb is a module under tasks and not gracedb-client
                gracedb.set_preferred_event(superevent['superevent_id'],
                                            superevent['preferred_event'],
                                            gid)
                break
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
        log.debug('4th if: Update the pointer')
        for entry in s_event_dict['superevents']:
            if entry['superevent_id'] == sid:
                break
        # if the preferred_event entry does not exists for some reason
        if not entry['preferred_event']:
            # FIXME: To be implemented
            raise NotImplementedError
        preferred_event = entry['preferred_event']
        # logic to decide if new event is preferred
        gracedb.set_preferred_event(entry['superevent_id'],
                                    preferred_event, gid)
    # Condition else
    else:
        log.critical('Unhandled by parse_trigger, passing...')
