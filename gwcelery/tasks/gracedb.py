"""Communication with GraceDB."""
from ligo.gracedb import rest
from celery.utils.log import get_task_logger

from ..import app
from ..util import PromiseProxy

client = PromiseProxy(rest.GraceDb,
                      ('https://' + app.conf.gracedb_host + '/api/',))

log = get_task_logger(__name__)


def task(*args, **kwargs):
    return app.task(*args, **kwargs, autoretry_for=(TimeoutError,),
                    default_retry_delay=20.0, retry_backoff=True,
                    retry_kwargs=dict(max_retries=10))


@task(shared=False)
def create_event(filecontents, search, pipeline, group):
    """Create an event in GraceDb."""
    response = client.createEvent(group=group, pipeline=pipeline,
                                  filename='initial.data', search=search,
                                  filecontents=filecontents)
    return response.json()['graceid']


@task(ignore_result=True, shared=False)
def create_label(label, graceid):
    """Create a label in GraceDb."""
    client.writeLabel(graceid, label)


@task(ignore_result=True, shared=False)
def create_signoff(status, comment, signoff_type, graceid):
    """Create a label in GraceDb."""
    client.create_signoff(graceid, signoff_type, status, comment)


@task(ignore_result=True, shared=False)
def create_tag(filename, tag, graceid):
    """Create a tag in GraceDb."""
    log = get_log(graceid)
    entry, = (e for e in log if e['filename'] == filename)
    log_number = entry['N']
    client.addTag(graceid, log_number, tag)


@task(shared=False)
def create_voevent(graceid, voevent_type, **kwargs):
    """Create a VOEvent.

    Returns
    -------
    str
        The filename of the new VOEvent.
    """
    response = client.createVOEvent(graceid, voevent_type, **kwargs).json()
    return response['filename']


@task(shared=False)
def download(filename, graceid):
    """Download a file from GraceDB."""
    return client.files(graceid, filename, raw=True).read()


@task(ignore_result=True, shared=False)
def expose(graceid):
    """Expose an event to the public."""
    client.modify_permissions(graceid, 'expose')


@task(shared=False)
def get_events(query=None, orderby=None, count=None, columns=None):
    """Get events from GraceDb."""
    return list(client.events(query=query, orderby=orderby,
                count=count, columns=columns))


@task(shared=False)
def get_event(graceid):
    """Retrieve an event from GraceDb."""
    return client.event(graceid).json()


@task(shared=False)
def get_labels(graceid):
    """Get all labels for an event in GraceDb."""
    return {row['name'] for row in client.labels(graceid).json()['labels']}


@task(shared=False)
def get_log(graceid):
    """Get all log messages for an event in GraceDb."""
    return client.logs(graceid).json()['log']


@task(shared=False)
def get_superevent(graceid):
    """Retrieve a superevent from GraceDb."""
    return client.superevent(graceid).json()


@task(shared=False)
def replace_event(graceid, payload):
    """Get an event from GraceDb."""
    client.replaceEvent(graceid, 'initial.data', filecontents=payload)


@task(ignore_result=True, shared=False)
def upload(filecontents, filename, graceid, message, tags=None):
    """Upload a file to GraceDB."""
    # FIXME: it would be more elegant to have `tags=()` in the kwargs, but
    # gracedb-client does not understand tuples of tags.
    # See https://git.ligo.org/lscsoft/gracedb-client/issues/5
    if tags is None:
        tags = []
    client.writeLog(graceid, message, filename, filecontents, tags)


@app.task(shared=False)
def get_superevents(query):
    """List matching superevents in gracedb.

    Parameters
    ----------
    query : str
        query to be passed to :meth:`superevents`

    Returns
    -------
    superevents : list
        The list of the superevents.
    """
    return list(client.superevents(query=query, orderby='t_0'))


@task(ignore_result=True, shared=False)
def update_superevent(superevent_id, t_start=None,
                      t_end=None, t_0=None, preferred_event=None):
    """
    Update superevent information. Wrapper around
    :meth:`updateSuperevent`

    Parameters
    ----------
    superevent_id : str
        superevent uid
    t_start : float
        start of superevent time window, unchanged if None
    t_end : float
        end of superevent time window, unchanged if None
    t_0 : float
        superevent t_0, unchanged if None
    preferred_event : str
        uid of the preferred event, unchanged if None
    """
    client.updateSuperevent(superevent_id, t_start=t_start, t_end=t_end,
                            t_0=t_0, preferred_event=preferred_event)


@task(ignore_result=True, shared=False)
def create_superevent(graceid, t0, d_t_start, d_t_end, category):
    """Create new superevent in GraceDb with `graceid`

    Parameters
    ----------
    graceid : str
        graceid with which superevent is created.
    t0 : float
        `t_0` parameter of superevent
    d_t_start : float
        superevent `t_start` = `t0 - d_t_start`
    d_t_end : float
        superevent `t_end` = `t0 + t_end`
    category : str
        superevent category
    """
    ts = t0 - d_t_start
    te = t0 + d_t_end
    client.createSuperevent(ts, t0, te, preferred_event=graceid,
                            category=category)


@task(ignore_result=True, shared=False)
def add_event_to_superevent(superevent_id, graceid):
    """Add an event to a superevent in GraceDb."""
    client.addEventToSuperevent(superevent_id, graceid)
