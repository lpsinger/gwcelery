"""
Integration of the Celery logging system with `Sentry <https://sentry.io>`_.
"""
from urllib.parse import urlparse, urlunparse

from celery.utils.log import get_logger
from safe_netrc import netrc, NetrcParseError
import sentry_sdk
from sentry_sdk.integrations import celery, flask

from . import _version
from .util import SPHINX

log = get_logger(__name__)

__all__ = ('configure', 'DSN')

DSN = 'https://sentry.io/1425216'
"""Sentry data source name (DSN)."""


def configure():
    """Configure Sentry logging integration for Celery according to the
    `official instructions <https://docs.sentry.io/platforms/python/celery/>`_.

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
                    integrations=[celery.CeleryIntegration(),
                                  flask.FlaskIntegration()])
