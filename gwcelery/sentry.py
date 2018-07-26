"""
Integration of the Celery logging system with `Sentry <https://sentry.io>`_.
"""
from urllib.parse import urlparse, urlunparse

from celery.utils.log import get_logger
import raven
import raven.contrib.celery
from safe_netrc import netrc, NetrcParseError

from .util import SPHINX

log = get_logger(__name__)

__all__ = ('configure', 'DSN')

DSN = 'http://emfollow.ldas.cit:9000//2'
"""Sentry :ref:`data source name <configure-the-dsn>`."""


def configure():
    """Configure Sentry logging integration for Celery according to the
    `official instructions
    <https://docs.sentry.io/clients/python/integrations/celery/>`_.

    Add the API key username/pasword pair to your netrc file.
    """
    # Catching NetrcParseError confuses sphinx.
    if SPHINX:  # pragma: no cover
        return

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

    username, _, password = auth
    dsn = urlunparse(
        (scheme, '{}:{}@{}'.format(username, password, netloc), *rest))
    client = raven.Client(dsn)
    raven.contrib.celery.register_logger_signal(client)
    raven.contrib.celery.register_signal(client)
