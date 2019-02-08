import logging
import os
import stat
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse

import pytest

from .. import __version__, app, sentry


@pytest.fixture
def netrcfile(monkeypatch, tmpdir):
    filename = str(tmpdir / 'netrc')
    monkeypatch.setenv('NETRC', filename)
    with open(filename, 'w') as f:
        os.fchmod(f.fileno(), stat.S_IRWXU)
    yield filename


@patch('sentry_sdk.init')
@patch('sentry_sdk.integrations.celery.CeleryIntegration')
@patch('sentry_sdk.integrations.flask.FlaskIntegration')
def test_sentry_configure(mock_flask_integration, mock_celery_integration,
                          mock_sdk_init, netrcfile, caplog):
    caplog.set_level(logging.ERROR)
    sentry.configure()
    record, = caplog.records
    assert 'Disabling Sentry integration' in record.message
    mock_celery_integration.assert_not_called()
    mock_sdk_init.assert_not_called()

    scheme, netloc, *rest = urlparse(sentry.DSN)
    with open(netrcfile, 'w') as f:
        print('machine', netloc, 'login', 'foo', 'password', 'bar', file=f)
    sentry.configure()
    dsn = urlunparse((scheme, 'foo@' + netloc, *rest))
    environment = app.conf['sentry_environment']
    release = 'gwcelery-' + __version__
    mock_celery_integration.assert_called_once_with()
    mock_sdk_init.assert_called_once_with(
        dsn, environment=environment, release=release,
        integrations=[
            mock_celery_integration.return_value,
            mock_flask_integration.return_value])
