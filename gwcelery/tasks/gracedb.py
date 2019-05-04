"""Communication with GraceDB."""
import functools

from ligo.gracedb import rest
from celery.utils.log import get_task_logger

from ..import app
from ..util import PromiseProxy

client = PromiseProxy(rest.GraceDb,
                      ('https://' + app.conf.gracedb_host + '/api/',))

log = get_task_logger(__name__)


class RetryableHTTPError(rest.HTTPError):
    """Exception class for server-side HTTP errors that we should retry."""


def catch_retryable_http_errors(f):
    """Decorator to capture server-side errors that we should retry.

    We retry HTTP status 502 (Bad Gateway), 503 (Service Unavailable), and
    504 (Gateway Timeout).
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except rest.HTTPError as e:
            if e.status in {502, 503, 504}:
                raise RetryableHTTPError(e.status, e.reason, e.message)
            else:
                raise

    return wrapper


def task(*args, **kwargs):
    return app.task(*args, **kwargs,
                    autoretry_for=(RetryableHTTPError, TimeoutError),
                    default_retry_delay=20.0, retry_backoff=True,
                    retry_kwargs=dict(max_retries=10))


@task(shared=False)
@catch_retryable_http_errors
def create_event(filecontents, search, pipeline, group):
    """Create an event in GraceDb."""
    response = client.createEvent(group=group, pipeline=pipeline,
                                  filename='initial.data', search=search,
                                  filecontents=filecontents)
    return response.json()['graceid']


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_label(label, graceid):
    """Create a label in GraceDb."""
    try:
        client.writeLabel(graceid, label).json()
    except rest.HTTPError as e:
        # If we got a 400 error because no change was made, then ignore
        # the exception and return successfully to preserve idempotency.
        if e.message != \
                b'"The fields superevent, label must make a unique set."':
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_signoff(status, comment, signoff_type, graceid):
    """Create a label in GraceDb."""
    client.create_signoff(graceid, signoff_type, status, comment).json()


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_tag(filename, tag, graceid):
    """Create a tag in GraceDb."""
    log = get_log(graceid)
    entry, = (e for e in log if e['filename'] == filename)
    log_number = entry['N']
    client.addTag(graceid, log_number, tag).json()


@task(shared=False)
@catch_retryable_http_errors
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
@catch_retryable_http_errors
def download(filename, graceid):
    """Download a file from GraceDB."""
    return client.files(graceid, filename, raw=True).read()


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def expose(graceid):
    """Expose an event to the public."""
    client.modify_permissions(graceid, 'expose').json()


@task(shared=False)
@catch_retryable_http_errors
def get_events(query=None, orderby=None, count=None, columns=None):
    """Get events from GraceDb."""
    return list(client.events(query=query, orderby=orderby,
                count=count, columns=columns))


@task(shared=False)
@catch_retryable_http_errors
def get_event(graceid):
    """Retrieve an event from GraceDb."""
    return client.event(graceid).json()


@task(shared=False)
@catch_retryable_http_errors
def get_labels(graceid):
    """Get all labels for an event in GraceDb."""
    return {row['name'] for row in client.labels(graceid).json()['labels']}


@task(shared=False)
@catch_retryable_http_errors
def get_log(graceid):
    """Get all log messages for an event in GraceDb."""
    return client.logs(graceid).json()['log']


@task(shared=False)
@catch_retryable_http_errors
def get_superevent(graceid):
    """Retrieve a superevent from GraceDb."""
    return client.superevent(graceid).json()


@task(shared=False)
@catch_retryable_http_errors
def replace_event(graceid, payload):
    """Get an event from GraceDb."""
    client.replaceEvent(graceid, 'initial.data', filecontents=payload).json()


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def upload(filecontents, filename, graceid, message, tags=()):
    """Upload a file to GraceDB."""
    client.writeLog(graceid, message, filename, filecontents, tags).json()


@app.task(shared=False)
@catch_retryable_http_errors
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
@catch_retryable_http_errors
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
    try:
        client.updateSuperevent(superevent_id,
                                t_start=t_start, t_end=t_end, t_0=t_0,
                                preferred_event=preferred_event).json()
    except rest.HTTPError as e:
        # If we got a 400 error because no change was made, then ignore
        # the exception and return successfully to preserve idempotency.
        if e.message != b'"Request would not modify the superevent"':
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
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
                            category=category).json()


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def add_event_to_superevent(superevent_id, graceid):
    """Add an event to a superevent in GraceDb."""
    client.addEventToSuperevent(superevent_id, graceid).json()
