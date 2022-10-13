"""Communication with GraceDB."""
from requests.exceptions import ConnectionError, HTTPError
import functools
import re

from celery.utils.log import get_task_logger
import gracedb_sdk

from ..import app
from ..util import PromiseProxy

client = PromiseProxy(gracedb_sdk.Client,
                      ('https://' + app.conf.gracedb_host + '/api/',),
                      {'fail_if_noauth': True, 'cert_reload': True})

log = get_task_logger(__name__)


class RetryableHTTPError(HTTPError):
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
        except HTTPError as e:
            if e.response.status_code in {408, 429, 502, 503, 504}:
                raise RetryableHTTPError(
                    *e.args, request=e.request, response=e.response)
            else:
                raise

    return wrapper


def task(*args, **kwargs):
    return app.task(*args, **kwargs,
                    autoretry_for=(
                        ConnectionError, RetryableHTTPError, TimeoutError),
                    default_retry_delay=20.0, retry_backoff=True,
                    retry_kwargs=dict(max_retries=10))


versioned_filename_regex = re.compile(
    r'^(?P<filename>.*?)(?:,(?P<file_version>\d+))?$')


def _parse_versioned_filename(versioned_filename):
    match = versioned_filename_regex.fullmatch(versioned_filename)
    filename = match['filename']
    file_version = match['file_version']
    if file_version is not None:
        file_version = int(file_version)
    return filename, file_version


@task(shared=False)
@catch_retryable_http_errors
def create_event(filecontents, search, pipeline, group, labels=()):
    """Create an event in GraceDB."""
    response = client.events.create(group=group, pipeline=pipeline,
                                    filename='initial.data', search=search,
                                    filecontents=filecontents, labels=labels)
    return response


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_label(label, graceid):
    """Create a label in GraceDB."""
    try:
        client.events[graceid].labels.create(label)
    except HTTPError as e:
        # If we got a 400 error because no change was made, then ignore
        # the exception and return successfully to preserve idempotency.
        messages = {
            b'"The \'ADVREQ\' label cannot be applied to request a signoff '
            b'because a related signoff already exists."',

            b'"The fields superevent, name must make a unique set."'
        }
        if e.response.content not in messages:
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def remove_label(label, graceid):
    """Remove a label in GraceDB."""
    try:
        client.events[graceid].labels.delete(label)
    except HTTPError as e:
        # If the label did not exist, then GraceDB will return a 404 error.
        # Don't treat this as a failure because we got what we wanted: for the
        # label to be removed.
        if e.response.status_code != 404:
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_signoff(status, comment, signoff_type, graceid):
    """Create a signoff in GraceDB."""
    try:
        client.superevents[graceid].signoff(signoff_type, status, comment)
    except HTTPError as e:
        # If we got a 400 error because the signoff was already applied,
        # then ignore the exception and return successfully to preserve
        # idempotency.
        message = b'The fields superevent, instrument must make a unique set'
        if message not in e.response.content:
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def create_tag(filename, tag, graceid):
    """Create a tag in GraceDB."""
    filename, file_version = _parse_versioned_filename(filename)
    log = get_log(graceid)
    if file_version is None:
        *_, entry = (e for e in log if e['filename'] == filename)
    else:
        *_, entry = (e for e in log if e['filename'] == filename
                     and e['file_version'] == file_version)
    log_number = entry['N']
    try:
        client.events[graceid].logs[log_number].tags.create(tag)
    except HTTPError as e:
        # If we got a 400 error because no change was made, then ignore
        # the exception and return successfully to preserve idempotency.
        message = b'"Tag is already applied to this log message"'
        if e.response.content != message:
            raise


@task(shared=False)
@catch_retryable_http_errors
def create_voevent(graceid, voevent_type, **kwargs):
    """Create a VOEvent.

    Returns
    -------
    str
        The filename of the new VOEvent.

    """
    response = client.events[graceid].voevents.create(
        voevent_type=voevent_type, **kwargs)
    return response['filename']


@task(shared=False)
@catch_retryable_http_errors
def download(filename, graceid):
    """Download a file from GraceDB."""
    with client.events[graceid].files[filename].get() as f:
        return f.read()


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def expose(graceid):
    """Expose an event to the public.

    Notes
    -----
    If :obj:`~gwcelery.conf.expose_to_public` is False, then this because a
    no-op.

    """
    if app.conf['expose_to_public']:
        client.superevents[graceid].expose()


@task(shared=False)
@catch_retryable_http_errors
def get_events(query, **kwargs):
    """Get events from GraceDB."""
    return list(client.events.search(query=query, **kwargs))


@task(shared=False)
@catch_retryable_http_errors
def get_event(graceid):
    """Retrieve an event from GraceDB."""
    return client.events[graceid].get()


@task(shared=False)
@catch_retryable_http_errors
def get_group(graceid):
    """Retrieve the search field of an event from GraceDB."""
    return client.events[graceid].get()['group']


@task(shared=False)
@catch_retryable_http_errors
def get_search(graceid):
    """Retrieve the search field of an event from GraceDB."""
    return client.events[graceid].get()['search']


@task(shared=False)
@catch_retryable_http_errors
def get_labels(graceid):
    """Get all labels for an event in GraceDB."""
    return {row['name'] for row in client.events[graceid].labels.get()}


@task(shared=False)
@catch_retryable_http_errors
def get_log(graceid):
    """Get all log messages for an event in GraceDB."""
    return client.events[graceid].logs.get()


@task(shared=False)
@catch_retryable_http_errors
def get_superevent(graceid):
    """Retrieve a superevent from GraceDB."""
    return client.superevents[graceid].get()


@task(shared=False)
@catch_retryable_http_errors
def replace_event(graceid, payload):
    """Get an event from GraceDB."""
    return client.events.update(graceid, filecontents=payload)


@task(shared=False)
@catch_retryable_http_errors
def upload(filecontents, filename, graceid, message, tags=()):
    """Upload a file to GraceDB."""
    result = client.events[graceid].logs.create(
        comment=message, filename=filename,
        filecontents=filecontents, tags=tags)
    return '{},{}'.format(result['filename'], result['file_version'])


@app.task(shared=False)
@catch_retryable_http_errors
def get_superevents(query, **kwargs):
    """List matching superevents in gracedb.

    Parameters
    ----------
    *args
        arguments passed to :meth:`GraceDb.superevents`
    **kwargs
        keyword arguments passed to :meth:`GraceDb.superevents`

    Returns
    -------
    superevents : list
        The list of the superevents.

    """
    return list(client.superevents.search(query=query, **kwargs))


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def update_superevent(superevent_id, t_start=None,
                      t_end=None, t_0=None, preferred_event=None,
                      em_type=None, time_coinc_far=None,
                      space_coinc_far=None):
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
        client.superevents.update(
            superevent_id, t_start=t_start, t_end=t_end, t_0=t_0,
            preferred_event=preferred_event, em_type=em_type,
            time_coinc_far=time_coinc_far, space_coinc_far=space_coinc_far)
    except HTTPError as e:
        # If we got a 400 error because no change was made, then ignore
        # the exception and return successfully to preserve idempotency.
        error_msg = b'"Request would not modify the superevent"'
        if not (e.response.status_code == 400
                and e.response.content == error_msg):
            raise


@task(shared=False)
@catch_retryable_http_errors
def create_superevent(graceid, t0, t_start, t_end):
    """Create new superevent in GraceDB with `graceid`

    Parameters
    ----------
    graceid : str
        graceid with which superevent is created.
    t0 : float
        ``t_0`` parameter of superevent
    t_start : float
        ``t_start`` parameter of superevent
    t_end : float
        ``t_end`` parameter of superevent

    """
    try:
        response = client.superevents.create(
            t_start=t_start, t_0=t0, t_end=t_end, preferred_event=graceid)
        return response['superevent_id']
    except HTTPError as e:
        error_msg = b'is already assigned to a Superevent'
        if not (e.response.status_code == 400
                and error_msg in e.response.content):
            raise


@task(ignore_result=True, shared=False)
@catch_retryable_http_errors
def add_event_to_superevent(superevent_id, graceid):
    """Add an event to a superevent in GraceDB."""
    try:
        client.superevents[superevent_id].add(graceid)
    except HTTPError as e:
        error_msg = b'is already assigned to a Superevent'
        if not (e.response.status_code == 400
                and error_msg in e.response.content):
            raise
