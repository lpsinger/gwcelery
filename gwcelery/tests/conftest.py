from unittest import mock

from celery.contrib.testing.app import UnitLogging
import pytest
from pytest_socket import disable_socket

from .. import app
from .process import starter  # noqa: F401


@pytest.fixture(scope='session', autouse=True)
def noop_celery_config():
    """Ensure that the Celery app is disconnected from live services."""
    new_conf = dict(
        broker_url='redis://redis.invalid',
        result_backend='redis://redis.invalid',
        voevent_broadcaster_address='127.0.0.1:53410',
        voevent_broadcaster_whitelist=['127.0.0.0/8'],
        voevent_receiver_address='gcn.invalid:8099',
        task_always_eager=True,
        task_eager_propagates=True,
        lvalert_host='lvalert.invalid',
        gracedb_host='gracedb.invalid',
        expose_to_public=True
    )
    tmp = {key: app.conf[key] for key in new_conf.keys()}
    app.conf.update(new_conf)
    yield
    app.conf.update(tmp)


@pytest.fixture
def celery_config():
    """Celery application configuration for tests that need a real worker."""
    return dict(
        broker_url='memory://',
        result_backend='cache+memory://',
        task_always_eager=False,
        task_eager_propagates=False,
    )


@pytest.fixture
def celery_worker_parameters():
    return dict(perform_ping_check=False)


@pytest.fixture
def celery_app(celery_config, celery_enable_logging, monkeypatch):
    new_conf = celery_config
    tmp = {key: app.conf[key] for key in new_conf.keys()}
    app.conf.update(new_conf)
    if not celery_enable_logging:
        monkeypatch.setattr(app, 'log', UnitLogging(app))
    yield app
    app.conf.update(tmp)


@pytest.fixture(autouse=True)
def fake_gracedb_client(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.url = 'https://gracedb.invalid/api/'
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', mock_client)


@pytest.fixture(autouse=True)
def fake_legacy_gracedb_client(monkeypatch):
    mock_client = mock.MagicMock()
    mock_client.url = 'https://gracedb.invalid/api/'
    monkeypatch.setattr('gwcelery.tasks.legacy_gracedb.client', mock_client)


def pytest_runtest_setup():
    # Celery caches the backend instance.
    # Since we switch backends between unit tests, make sure that the cached
    # backend is cleared.
    try:
        del app._local.backend
    except AttributeError:
        pass

    disable_socket()
