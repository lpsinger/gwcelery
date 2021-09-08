from unittest import mock

from kombu.utils import cached_property
from celery.contrib.testing.app import UnitLogging
import pytest
from pytest_socket import disable_socket

from .. import app
from .process import starter  # noqa: F401


def nuke_celery_backend():
    """Clear the cached Celery backend.

    The Celery application object caches a lot of instance members that are
    affected by the application configuration. Since we are changing the
    configuration between tests, we need to make sure that all of the cached
    application state is reset.

    FIXME: The pytest celery plugin does not seem like it is really designed
    to use a pre-existing application object; it seems like it is designed to
    create a test application.

    """
    app._pool = None
    for key, value in app.__class__.__dict__.items():
        if isinstance(value, cached_property):
            try:
                del app.__dict__[key]
            except KeyError:
                pass
    app._local.__dict__.clear()


@pytest.fixture
def reset_celery_backend():
    """Nuke the celery backend before and after the test."""
    nuke_celery_backend()
    yield
    nuke_celery_backend()


@pytest.fixture
def update_celery_config():
    """Monkey patch the Celery application configuration."""
    tmp = {}

    def update(new_conf):
        tmp.update({key: app.conf[key] for key in new_conf.keys()})
        app.conf.update(new_conf)

    yield update
    app.conf.update(tmp)


@pytest.fixture
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


def pytest_configure(config):
    config.addinivalue_line(
        'markers', 'live_worker: run test using a live Celery worker')


def pytest_collection_modifyitems(session, config, items):
    # FIXME: We are reordering the tests so that the ones that use a live
    # celery worker run last. Otherwise, they cause problems with other
    # tests that use the 'caplog' fixture. We don't understand why this is.
    # Remove this hack if and when we figure it out.
    items[:] = sorted(
        items,
        key=lambda item: item.get_closest_marker('live_worker') is not None)


def pytest_runtest_setup(item):
    disable_socket()


@pytest.fixture(autouse=True)
def maybe_celery_worker(request):
    if request.node.get_closest_marker('live_worker') is None:
        fixture = 'noop_celery_config'
    else:
        fixture = 'celery_worker'
    request.getfixturevalue(fixture)
