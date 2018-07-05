from pkg_resources import resource_filename
import pytest

from ..celery import app
from ..tasks import detchar


@pytest.fixture
def llhoft_dir_pass():
    old = app.conf['llhoft_dir']
    app.conf['llhoft_dir'] = resource_filename(__name__, 'data/llhoft/pass')
    yield
    app.conf['llhoft_dir'] = old


@pytest.fixture
def llhoft_dir_fail():
    old = app.conf['llhoft_dir']
    app.conf['llhoft_dir'] = resource_filename(__name__, 'data/llhoft/fail')
    yield
    app.conf['llhoft_dir'] = old


def test_read_gwf(llhoft_dir_fail):
    assert len(detchar.read_gwf('L1', 'GDS-CALIB_STATE_VECTOR',
                                0, 16384.0))/16 == 16384.0


def test_check_vector(llhoft_dir_pass):
    channel = 'DMT-DQ_VECTOR'
    ifo = 'H1'
    start = 1214714160
    end = 1214714164
    assert detchar.check_vector(ifo, channel, start, end, 0b11, 'any')
    assert not detchar.check_vector(ifo, channel, start, end, 0b1111, 'any')
