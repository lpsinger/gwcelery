"""Communication with GraceDB using the legacy GraceDB client."""
import functools
from http.client import HTTPException
from socket import gaierror

from ligo.gracedb import rest

from ..import app
from ..util import PromiseProxy

client = PromiseProxy(rest.GraceDb,
                      ('https://' + app.conf.gracedb_host + '/api/',),
                      {'fail_if_noauth': True, 'reload_certificate': True})


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
            if e.status in {429, 502, 503, 504}:
                raise RetryableHTTPError(e.status, e.reason, e.message)
            else:
                raise

    return wrapper


def task(*args, **kwargs):
    return app.task(*args, **kwargs,
                    autoretry_for=(gaierror, RetryableHTTPError,
                                   TimeoutError, HTTPException),
                    default_retry_delay=20.0, retry_backoff=True,
                    retry_kwargs=dict(max_retries=10))
