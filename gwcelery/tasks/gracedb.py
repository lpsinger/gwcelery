"""Communication with GraceDB."""
import os
import sys

from ligo.gracedb import rest
from celery.local import PromiseProxy
from celery.utils.log import get_task_logger

from ..celery import app

# Defer initializing the GraceDb REST client until it is needed,
# because if the user lacks valid credentials, then the API will
# raise an exception as soon as it is instantiated---which would
# otherwise make it impossible to import this module without first
# logging in.
#
# FIXME: sphinx gets confused by PromiseProxy and prints:
#     Recursion error:
#     maximum recursion depth exceeded
# so don't create the proxy if we are being run by sphinx.
prog = os.path.basename(sys.argv[0])
if prog != 'sphinx-build' and 'build_sphinx' not in sys.argv:
    client = PromiseProxy(rest.GraceDb,
                          ('https://' + app.conf.gracedb_host + '/api/',))

log = get_task_logger(__name__)


@app.task(shared=False)
def create_event(filecontents, search, pipeline, group):
    """Create an event in GraceDb."""
    response = client.createEvent(group=group, pipeline=pipeline,
                                  filename='initial.data', search=search,
                                  filecontents=filecontents)
    return response.json()['graceid']


@app.task(ignore_result=True, shared=False)
def create_tag(tag, n, graceid):
    """Create a tag in GraceDb."""
    client.createTag(graceid, n, tag)


@app.task(shared=False)
def download(filename, graceid):
    """Download a file from GraceDB."""
    return client.files(graceid, filename, raw=True).read()


@app.task(shared=False)
def get_event(graceid):
    """Retrieve an event from GraceDb."""
    return client.event(graceid).json()


@app.task(shared=False)
def get_log(graceid):
    """Get all log messages for an event in GraceDb."""
    return client.logs(graceid).json()['log']


@app.task(ignore_result=True, shared=False)
def upload(filecontents, filename, graceid, message, tags=()):
    """Upload a file to GraceDB."""
    client.writeLog(graceid, message, filename, filecontents, tags)


@app.task(shared=False)
def get_superevent(gid):
    """Iterate through superevents in gracedb and return sid if
    gid exists in the association.

    Parameters
    ----------
    gid : str
        uid of the trigger to be checked

    Returns
    -------
    superevent_id : str
        uid of the superevent. None if not found
    preferred_flag : bool
        True if gid is found and it is preferred. None if not found.
    r : dict
        The JSON packet of the superevent. None if not found.
    """
    r = client.get(client.service_url+"superevents/")
    r_json = r.json()
    superevents = r_json['superevents']
    for superevent in superevents:
        preferred_flag = False
        # check preferred_event first
        if gid == superevent['preferred_event']:
            preferred_flag = True
            log.info('Found association (Preferred) %s <-> %s',
                     gid, superevent['superevent_id'])
            return superevent['superevent_id'], preferred_flag, r_json
        # then check the gw_events
        elif gid in superevent['gw_events']:
            log.info('Found association (NOT Preferred) %s <-> %s',
                     gid, superevent['superevent_id'])
            return superevent['superevent_id'], preferred_flag, r_json
    return None, False, r_json


@app.task(ignore_result=True, shared=False)
def set_preferred_event(sid, preferred_event, gid):
    """
    Update superevent with the new trigger id based on
    FAR values.

    Parameters
    ----------
    sid : str
        superevent uid
    preferred_event : str
        preferred event id of the superevent
    gid : str
        uid of the new trigger
    """
    r_new_event = client.event(gid).json()
    r_preferred_event = client.event(preferred_event).json()
    if r_new_event['far'] < r_preferred_event['far']:
        client.updateSuperevent(sid,
                                preferred_event=r_new_event['graceid'])


@app.task(ignore_result=True, shared=False)
def create_superevent(payload, d_t_start=5, d_t_end=5):
    """
    Create new superevent in GraceDb with preferred G event.
    """
    t0 = payload['object']['gpstime']
    gid = payload['uid']
    ts = t0 - d_t_start
    te = t0 + d_t_end
    client.createSuperevent(ts, t0, te, preferred_event=gid)
    log.info('Successfully created superevent')


@app.task(ignore_result=True, shared=False)
def add_event_to_superevent(sid, gid):
    """Wrapper for GraceDb.addEventToSuperevent.
    Can be called in async if required
    """
    client.addEventToSuperevent(sid, gid)
