from unittest import mock

from kombu.utils import cached_property
from celery.contrib.testing.app import UnitLogging
import pytest
from pytest_socket import disable_socket

from .. import app
from .process import starter  # noqa: F401


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


@pytest.fixture(autouse=True)
def no_sockets():
    disable_socket()


#
# The following methods override `fixtures provided by the Celery pytest plugin
# <https://docs.celeryproject.org/en/stable/userguide/testing.html#fixtures>`_.
#


@pytest.fixture
def celery_config(request):
    """Prepare Celery application configuration for unit tests."""
    # If this unit test does not have the `@pytest.mark.live_worker` mark,
    # then turn on eager mode.
    eager = not request.node.get_closest_marker('live_worker')

    return dict(
        broker_url='memory://',
        result_backend='cache+memory://',
        worker_hijack_root_logger=False,
        task_always_eager=eager,
        task_eager_propagates=eager,
        voevent_broadcaster_address='127.0.0.1:53410',
        voevent_broadcaster_whitelist=['127.0.0.0/8'],
        voevent_receiver_address='gcn.invalid:8099',
        lvalert_host='lvalert.invalid',
        gracedb_host='gracedb.invalid',
        expose_to_public=True
    )


@pytest.fixture
def celery_worker_parameters():
    """Prepare Celery worker configuration for unit tests."""
    # Disable the ping check on worker startup. The `ping` task is registered
    # on the Celery pytest plugin's default test app, but not on our app.
    return dict(perform_ping_check=False)


@pytest.fixture(autouse=True)
def celery_app(celery_config, celery_enable_logging, monkeypatch):
    """Prepare Celery application for unit tests.

    The original fixture returns a specially-created test application. This
    version substitutes our own (gwcelery's) application.
    """
    # Update the Celery application configuration.
    for key, value in celery_config.items():
        monkeypatch.setitem(app.conf, key, value)

    # Configure logging, if requested.
    if not celery_enable_logging:
        monkeypatch.setattr(app, 'log', UnitLogging(app))

    # Reset all of the cached Celery application properties.
    #
    # The Celery application object caches a lot of instance members that are
    # affected by the application configuration. Since we are changing the
    # configuration between tests, we need to make sure that all of the cached
    # application state is reset.
    #
    # First, reset all of the @cached_property members...
    for key, value in app.__class__.__dict__.items():
        if isinstance(value, cached_property):
            try:
                del app.__dict__[key]
            except KeyError:
                pass
    # Then, reset the thread-local storage.
    app._local.__dict__.clear()

    # Now, allow the unit test to run.
    yield app

    # Finally, reset the worker pool.
    app.close()


#
# The following `pytest hooks
# <https://docs.pytest.org/en/latest/how-to/writing_hook_functions.html>`_ and
# fixtures implement the `@pytest.mark.live_worker` decorator that indicates
# unit tests that use a live Celery worker (as opposed to eager mode).
#


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


@pytest.fixture(autouse=True)
def maybe_celery_worker(request):
    if request.node.get_closest_marker('live_worker'):
        request.getfixturevalue('celery_worker')
