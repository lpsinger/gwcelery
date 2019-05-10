import unittest

from ligo.gracedb import rest
import pytest
from pytest_socket import disable_socket

from .. import app
from .process import starter  # noqa: F401


@pytest.fixture(scope='session', autouse=True)
def celeryconf(tmp_path_factory):
    broker_url = 'redis+socket://' + str(
        tmp_path_factory.mktemp('sockets') / 'sock')
    new_conf = dict(
        broker_url=broker_url,
        result_backend=broker_url,
        voevent_broadcaster_address='127.0.0.1:53410',
        voevent_broadcaster_whitelist=['127.0.0.0/8'],
        voevent_receiver_address='gcn.invalid:8099',
        task_always_eager=True,
        task_eager_propagates=True,
        lvalert_host='lvalert.invalid',
        gracedb_host='gracedb.invalid'
    )
    tmp = {key: app.conf[key] for key in new_conf.keys()}
    app.conf.update(new_conf)
    yield
    app.conf.update(tmp)


@pytest.fixture(autouse=True)
def fake_gracedb_client(monkeypatch):
    mock_client = unittest.mock.create_autospec(rest.GraceDb)
    mock_client._service_url = 'https://gracedb.invalid/api/'
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', mock_client)
    yield


def pytest_runtest_setup():
    disable_socket()
