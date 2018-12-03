import logging
from unittest.mock import call, patch

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


@pytest.fixture
def gatedpipe():
    old = app.conf['uses_gatedhoft']
    app.conf['uses_gatedhoft'] = {'gatepipe': True}
    yield
    app.conf['uses_gatedhoft'] = old


@pytest.fixture
def gatedpipe_prepost():
    old = app.conf['check_vector_prepost']
    app.conf['check_vector_prepost'] = {'gatepipe': [0.5, 0.5]}
    yield
    app.conf['check_vector_prepost'] = old


def test_create_cache(llhoft_glob_fail):
    assert len(detchar.create_cache('L1')) == 1


def test_check_idq(llhoft_glob_pass):
    channel = 'H1:IDQ-PGLITCH_OVL_32_2048'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1')
    assert detchar.check_idq(cache, channel, start, end) == (
        'H1:IDQ-PGLITCH_OVL_32_2048', 0)


@patch('time.strftime', return_value='00:00:00 UTC Mon 01 Jan 2000')
@patch('socket.gethostname', return_value='test_host')
@patch('getpass.getuser', return_value='test_user')
def test_dqr_json(mock_time, mock_host, mock_user):
    state = "pass"
    summary = "72 and sunny!!"
    assert detchar.dqr_json(state, summary) == {
        'state': 'pass',
        'process_name': 'gwcelery.tasks.detchar',
        'process_version': 'unknown',
        'librarian': 'Geoffrey Mo (geoffrey.mo@ligo.org)',
        'date': '00:00:00 UTC Mon 01 Jan 2000',
        'hostname': 'test_host',
        'username': 'test_user',
        'summary': '72 and sunny!!',
        'figures': [],
        'tables': [],
        'links': ([
            {
                "href":
                "https://gwcelery.readthedocs.io/en/latest/gwcelery.tasks.detchar.html#gwcelery.tasks.detchar.check_vectors", # noqa
                "innerHTML": "a link to the documentation for this process"
            },
            {
                "href":
                "https://git.ligo.org/emfollow/gwcelery/blob/master/gwcelery/tasks/detchar.py",  # noqa
                "innerHTML": "a link to the source code in the gwcelery repo"
            }
        ]),
        'extra': []
    }


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


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.client.writeLog')
@patch('gwcelery.tasks.gracedb.create_label')
def test_check_vectors(mock_create_label, mock_write_log, mock_json,
                       llhoft_glob_pass, ifo_h1, ifo_h1_idq):
    event = {'search': 'AllSky', 'instruments': 'H1', 'pipeline': 'oLIB'}
    superevent_id = 'S12345a'
    start, end = 1216577977, 1216577979
    detchar.check_vectors(event, superevent_id, start, end)
    print(mock_write_log.mock_calls)
    calls = [
        call(
            'S12345a',
            ('detector state for active instruments is good.'
             ' For all instruments,'
             ' bits good (H1:NO_OMC_DCPD_ADC_OVERFLOW,'
             ' H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW, H1:HOFT_OK,'
             ' H1:OBSERVATION_INTENT), bad (), unknown()'
             ' within -0.5/+0.5 seconds of superevent'),
            tag_name=['data_quality']),
        call(
            'S12345a',
            'No HW injections found within -0.5/+0.5 seconds of superevent',
            tag_name=['data_quality']),
        call(
            'S12345a',
            ('iDQ glitch probabilities at both H1 and L1'
             ' are good (below {})'
             ' within -0.5/+0.5 seconds of superevent').format(
                 app.conf['idq_pglitch_thresh']),
            tag_name=['data_quality']),
        call(
            'S12345a',
            'DQR-compatible json generated from check_vectors results',
            'gwcelerydetcharcheckvectors-S12345a.json',
            '"dqrjson"',
            ['data_quality']),
    ]
    mock_write_log.assert_has_calls(calls, any_order=True)
    mock_create_label.assert_called_with('DQOK', 'S12345a')


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.client.writeLog')
@patch('gwcelery.tasks.gracedb.create_label')
def test_gatedhoft_skips_dmtvec(mock_create_label, mock_write_log, mock_json,
                                llhoft_glob_pass, ifo_h1, ifo_h1_idq,
                                gatedpipe, gatedpipe_prepost):
    event = {'search': 'AllSky', 'instruments': 'H1', 'pipeline': 'gatepipe'}
    superevent_id = 'S12345a'
    start, end = 1216577977, 1216577979
    detchar.check_vectors(event, superevent_id, start, end)
    mock_write_log.assert_has_calls([
            call('S12345a',
                 ('detector state for active instruments is good.'
                  ' For all instruments,'
                  ' bits good (H1:HOFT_OK,'
                  ' H1:OBSERVATION_INTENT), bad (), unknown()'
                  ' within -0.5/+0.5 seconds of superevent.'
                  ' Pipeline gatepipe uses gated h(t),'
                  ' LIGO DMT-DQ_VECTOR not checked.'),
                 tag_name=['data_quality'])], any_order=True
    )
