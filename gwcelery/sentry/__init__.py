"""Error telemetry for `Sentry <https://sentry.io>`_."""
from urllib.parse import urlparse, urlunparse

from celery.utils.log import get_logger
from safe_netrc import netrc, NetrcParseError
import sentry_sdk
from sentry_sdk.integrations import celery, flask, redis, tornado

from .. import _version
from ..util import SPHINX
from .integrations import condor, requests, subprocess

log = get_logger(__name__)

__all__ = ('configure', 'DSN')

DSN = 'https://sentry.io/1425216'
"""Sentry data source name (DSN)."""


def configure():
    """Configure Sentry logging integration for Celery.

    See the `official instructions for Celery integration
    <https://docs.sentry.io/platforms/python/celery/>`_.

    Notes
    -----
    Add the API key username/pasword pair to your netrc file.

    """
    # Catching NetrcParseError confuses sphinx.
    if SPHINX:  # pragma: no cover
        return

    # Delayed import
    from .. import app

    scheme, netloc, *rest = urlparse(DSN)

    try:
        auth = netrc().authenticators(netloc)
        if not auth:
            raise ValueError('No netrc entry found for {}'.format(netloc))
    except (NetrcParseError, OSError, ValueError):
        log.exception('Disabling Sentry integration because we could not load '
                      'the username and password for %s from the netrc file',
                      netloc)
        return

    # The "legacy" Sentry DSN requires a "public key" and a "private key",
    # which are transmitted as the username and password in the URL.
    # However, as of Sentry 9, then "private key" part is no longer required.
    username, _, _ = auth
    dsn = urlunparse(
        (scheme, '{}@{}'.format(username, netloc), *rest))
    version = 'gwcelery-{}'.format(_version.get_versions()['version'])
    environment = app.conf['sentry_environment']
    sentry_sdk.init(dsn, environment=environment, release=version,
                    integrations=[celery.CeleryIntegration(),
                                  condor.CondorIntegration(),
                                  flask.FlaskIntegration(),
                                  redis.RedisIntegration(),
                                  requests.RequestsIntegration(),
                                  subprocess.SubprocessIntegration(),
                                  tornado.TornadoIntegration()])
