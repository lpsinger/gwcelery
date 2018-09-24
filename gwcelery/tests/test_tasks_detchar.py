import logging
from unittest.mock import patch

from pkg_resources import resource_filename
import pytest

from ..import app
from ..tasks import detchar


@pytest.fixture
def llhoft_glob_pass():
    old = app.conf['llhoft_glob']
    app.conf['llhoft_glob'] = resource_filename(
        __name__, 'data/llhoft/pass/{detector}/*.gwf')
    yield
    app.conf['llhoft_glob'] = old


@pytest.fixture
def llhoft_glob_fail():
    old = app.conf['llhoft_glob']
    app.conf['llhoft_glob'] = resource_filename(
        __name__, 'data/llhoft/fail/{detector}/*.gwf')
    yield
    app.conf['llhoft_glob'] = old


@pytest.fixture
def ifo_h1():
    old = app.conf['llhoft_channels']
    app.conf['llhoft_channels'] = {
        'H1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
        'H1:GDS-CALIB_STATE_VECTOR': 'state_vector_bits'}
    yield
    app.conf['llhoft_channels'] = old


@pytest.fixture
def ifo_h1_idq():
    old = app.conf['idq_channels']
    app.conf['idq_channels'] = [
        'H1:IDQ-PGLITCH_OVL_32_2048']
    yield
    app.conf['idq_channels'] = old


def test_create_cache(llhoft_glob_fail):
    assert len(detchar.create_cache('L1')) == 1


def test_check_idq(llhoft_glob_pass):
    channel = 'H1:IDQ-PGLITCH_OVL_32_2048'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1')
    assert detchar.check_idq(cache, channel, start, end) == (
        'H1:IDQ-PGLITCH_OVL_32_2048', 0)


def test_check_vector(llhoft_glob_pass):
    channel = 'H1:DMT-DQ_VECTOR'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1')
    bits = detchar.dmt_dq_vector_bits
    assert detchar.check_vector(cache, channel, start, end, bits) == {
        'H1:NO_OMC_DCPD_ADC_OVERFLOW': True,
        'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW': True}


def test_check_vectors_skips_mdc(caplog):
    """Test that state vector checks are skipped for MDC events."""
    caplog.set_level(logging.INFO)
    detchar.check_vectors({'search': 'MDC', 'graceid': 'M1234'}, 'S123', 0, 1)
    messages = [record.message for record in caplog.records]
    assert 'Skipping state vector checks because M1234 is an MDC' in messages


@patch('gwcelery.tasks.gracedb.client.writeLog')
@patch('gwcelery.tasks.gracedb.create_label')
def test_check_vectors(mock_create_label, mock_write_log,
                       llhoft_glob_pass, ifo_h1, ifo_h1_idq):
    event = {'search': 'AllSky', 'instruments': 'H1', 'pipeline': 'oLIB'}
    superevent_id = 'S12345a'
    start, end = 1216577977, 1216577979
    detchar.check_vectors(event, superevent_id, start, end)
    mock_write_log.assert_called_with(
        'S12345a',
        ('detector state for active instruments is good. For all instruments,'
         ' bits good (H1:NO_OMC_DCPD_ADC_OVERFLOW,'
         ' H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW, H1:HOFT_OK,'
         ' H1:OBSERVATION_INTENT), bad (), unknown().'),
        tag_name=['data_quality'])
    mock_create_label.assert_called_with('DQOK', 'S12345a')
