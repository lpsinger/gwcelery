import pkg_resources
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import pytest

from .. import app

__all__ = ('app', 'celeryconf', 'patch', 'pkg_resources', 'pytest')


@pytest.fixture(scope='session', autouse=True)
def celeryconf():
    new_conf = dict(
        gcn_bind_address='127.0.0.1',
        gcn_bind_port=53410,
        gcn_remote_address='127.0.0.1',
        task_always_eager=True
    )
    tmp = {key: app.conf[key] for key in new_conf.keys()}
    app.conf.update(new_conf)
    yield
    app.conf.update(tmp)
