from contextlib import contextmanager
from unittest import mock

from celery.contrib.testing.app import UnitLogging
import pytest
from pytest_socket import disable_socket

from .. import app
from .process import starter  # noqa: F401


def nuke_celery_backend():
    """Clear the cached Celery backend.

    Some of our tests switch backend URLs. In order for the switch to take
    effect, we need to make sure that the cached backed object has been reset.

    """
    try:
        del app._local.backend
    except AttributeError:
        pass


@pytest.fixture
def reset_celery_backend():
    nuke_celery_backend()
    yield
    nuke_celery_backend()


@pytest.fixture
def update_celery_config():
    tmp = {}

    def update(new_conf):
        tmp.update({key: app.conf[key] for key in new_conf.keys()})
        app.conf.update(new_conf)

    yield update
    app.conf.update(tmp)


@pytest.fixture(autouse=True)
def noop_celery_config(reset_celery_backend, update_celery_config):
    """Ensure that the Celery app is disconnected from live services."""
    update_celery_config(dict(
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
    ))


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
def celery_app(celery_config, celery_enable_logging, reset_celery_backend,
               update_celery_config, monkeypatch):
    update_celery_config(celery_config)
    if not celery_enable_logging:
        monkeypatch.setattr(app, 'log', UnitLogging(app))
    yield app


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
    disable_socket()
