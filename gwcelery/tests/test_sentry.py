import logging
import os
import stat
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse

import pytest

from .. import sentry


@pytest.fixture
def netrcfile(monkeypatch, tmpdir):
    filename = str(tmpdir / 'netrc')
    monkeypatch.setenv('NETRC', filename)
    with open(filename, 'w') as f:
        os.fchmod(f.fileno(), stat.S_IRWXU)
    yield filename


@patch('raven.contrib.celery.register_logger_signal', autospec=True)
@patch('raven.contrib.celery.register_signal', autospec=True)
@patch('raven.Client', autospec=True)
def test_sentry_configure(mock_client, mock_register_signal,
                          mock_register_logger_signal, netrcfile, caplog):
    caplog.set_level(logging.ERROR)
    sentry.configure()
    record, = caplog.records
    assert 'Disabling Sentry integration' in record.message
    mock_client.assert_not_called()
    mock_register_signal.assert_not_called()
    mock_register_logger_signal.assert_not_called()

    scheme, netloc, *rest = urlparse(sentry.DSN)
    with open(netrcfile, 'w') as f:
        print('machine', netloc, 'login', 'foo', 'password', 'bar', file=f)
    sentry.configure()
    dsn = urlunparse((scheme, 'foo:bar@' + netloc, *rest))
    mock_client.assert_called_once_with(dsn)
    mock_register_signal.assert_called_once()
    mock_register_logger_signal.assert_called_once()
