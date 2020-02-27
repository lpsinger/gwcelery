"""Error telemetry for `Sentry <https://sentry.io>`_."""
from urllib.parse import urlparse, urlunparse
from subprocess import CalledProcessError
import os

from celery.utils.log import get_logger
from safe_netrc import netrc, NetrcParseError
import sentry_sdk
from sentry_sdk.integrations import celery, flask, redis, tornado

from . import _version
from .util import SPHINX

log = get_logger(__name__)

__all__ = ('configure', 'DSN')

DSN = 'https://sentry.io/1425216'
"""Sentry data source name (DSN)."""


def before_send(event, hint):
    """Capture stderr and stdout from CalledProcessError exceptions."""
    if 'exc_info' not in hint:
        return event

    _, e, _ = hint['exc_info']
    if not isinstance(e, CalledProcessError):
        return event

    breadcrumbs = event.get('breadcrumbs', [])
    if len(breadcrumbs) < 1:
        return event
    breadcrumb = breadcrumbs[0]

    for key in ['stderr', 'stdout']:
        value = getattr(e, key)
        if value:
            breadcrumb.setdefault('data', {})[key] = value.decode(
                errors='replace')
    return event


def _read_classad(filename):
    with open(filename) as f:
        for line in f:
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"')
            yield key, value


def _add_htcondor():
    """Record HTCondor job information in Sentry."""
    try:
        data = dict(_read_classad(os.environ['_CONDOR_JOB_AD']))
    except (KeyError, IOError):
        return
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag('htcondor.cluster_id', '{}.{}'.format(
            data['ClusterId'], data['ProcId']))


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
    from . import app

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
                    before_send=before_send,
                    integrations=[celery.CeleryIntegration(),
                                  flask.FlaskIntegration(),
                                  redis.RedisIntegration(),
                                  tornado.TornadoIntegration()])
    _add_htcondor()
