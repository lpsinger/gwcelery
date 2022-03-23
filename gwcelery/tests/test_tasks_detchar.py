from io import BytesIO
import logging
from pathlib import Path
from unittest.mock import call, patch

from astropy.time import Time
from gwpy.timeseries import Bits
import matplotlib.pyplot as plt
import numpy as np
import pytest

from ..import app
from ..import _version
from ..tasks import detchar


@pytest.fixture
def llhoft_glob_pass(monkeypatch):
    path = str(Path(__file__).parent / 'data/llhoft/pass/{detector}/*.gwf')
    yield monkeypatch.setitem(app.conf, 'llhoft_glob', path)


@pytest.fixture
def llhoft_glob_fail(monkeypatch):
    path = str(Path(__file__).parent / 'data/llhoft/fail/{detector}/*.gwf')
    yield monkeypatch.setitem(app.conf, 'llhoft_glob', path)


@pytest.fixture
def ifo_h1(monkeypatch):
    monkeypatch.setitem(app.conf, 'llhoft_channels', {
        'H1:DMT-DQ_VECTOR': 'dmt_dq_vector_bits',
        'H1:GDS-CALIB_STATE_VECTOR': 'ligo_state_vector_bits'})


@pytest.fixture
def ifo_h1_idq(monkeypatch):
    monkeypatch.setitem(
        app.conf, 'idq_channels', ['H1:IDQ-PGLITCH_OVL_32_2048'])


@pytest.fixture
def gatedpipe(monkeypatch):
    monkeypatch.setitem(app.conf, 'uses_gatedhoft', {'gatepipe': True})


@pytest.fixture
def gatedpipe_prepost(monkeypatch):
    monkeypatch.setitem(
        app.conf, 'check_vector_prepost', {'gatepipe': [0.5, 0.5]})


@pytest.fixture
def scan_strainname(monkeypatch):
    monkeypatch.setitem(
        app.conf, 'strain_channel_names', {'H1': 'H1:GWOSC-16KHZ_R1_STRAIN'})


def test_create_cache(llhoft_glob_fail):
    assert len(detchar.create_cache('L1', 1216577976, 1216577979)) == 1


@patch('gwcelery.tasks.detchar.find_urls', return_value=[])
def test_create_cache_old_data(mock_find, llhoft_glob_fail):
    start, end = 1198800018, 1198800028
    detchar.create_cache('L1', start, end)
    mock_find.assert_called()


expected_path = Path(__file__).parent / 'data/llhoft/omegascan/scanme.gwf'


@patch('gwcelery.tasks.detchar.create_cache', return_value=[expected_path])
def test_make_omegascan_worked(mock_create_cache, scan_strainname):
    durs = [1, 1, 1]
    t0 = 1126259463
    png = detchar.make_omegascan('H1', t0, durs)
    pngarray = plt.imread(BytesIO(png))
    # Test to see that the png is taller than 1400 pixels, indicating
    # presence of omegascan(s)
    assert plt.imshow(pngarray).get_extent()[2] > 1400


@patch('gwcelery.tasks.detchar.create_cache', return_value=[])
def test_make_omegascan_failed(mock_create_cache, scan_strainname):
    durs = [1, 1, 1]
    t0 = 1126259463
    png = detchar.make_omegascan('H1', t0, durs)
    pngarray = plt.imread(BytesIO(png))
    # Test to see that the png is shorter than 1500 pixels
    assert plt.imshow(pngarray).get_extent()[2] < 1500


@patch('gwcelery.tasks.detchar.make_omegascan.run',
       return_value=BytesIO().getvalue())
@patch('gwcelery.tasks.gracedb.upload.run')
def test_omegascan(mock_upload, mock_fig):
    t0 = 1126259463
    gid = "S1234"
    detchar.omegascan(t0, gid)
    mock_upload.assert_called_with(
        mock_fig(), "V1_omegascan.png", gid, "V1 omegascan",
        tags=['data_quality']
    )


def test_omegascan_skips_ew(caplog):
    """Test that omegascans are delayed for events in the future."""
    caplog.set_level(logging.INFO)
    detchar.omegascan(Time.now().gps + 99, 'S1234')
    messages = [record.message for record in caplog.records]
    assert 'Delaying omegascan because S1234 is in the future' in messages  # noqa: E501


def test_check_idq(llhoft_glob_pass):
    channel = 'H1:IDQ-PGLITCH_OVL_32_2048'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1', start, end)
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
        'process_version': _version.get_versions()['version'],
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
                "https://git.ligo.org/emfollow/gwcelery/blob/main/gwcelery/tasks/detchar.py",  # noqa
                "innerHTML": "a link to the source code in the gwcelery repo"
            }
        ]),
        'extra': []
    }


def test_check_vector(llhoft_glob_pass):
    channel = 'H1:DMT-DQ_VECTOR'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1', start, end)
    bit_defs = {channel_type: Bits(channel=bitdef['channel'],
                                   bits=bitdef['bits'])
                for channel_type, bitdef
                in app.conf['detchar_bit_definitions'].items()}
    assert detchar.check_vector(cache, channel, start, end,
                                bit_defs['dmt_dq_vector_bits']) == {
        'H1:NO_OMC_DCPD_ADC_OVERFLOW': True,
        'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW': True}


@patch('gwcelery.tasks.detchar.StateVector.read', return_value=np.asarray([]))
def test_check_vector_fails_on_empty(mock_statevector, llhoft_glob_pass):
    channel = 'H1:DMT-DQ_VECTOR'
    start, end = 1216577976, 1216577980
    cache = detchar.create_cache('H1', start, end)
    bit_defs = {channel_type: Bits(channel=bitdef['channel'],
                                   bits=bitdef['bits'])
                for channel_type, bitdef
                in app.conf['detchar_bit_definitions'].items()}
    assert detchar.check_vector(cache, channel, start, end,
                                bit_defs['dmt_dq_vector_bits']) == {
        'H1:NO_OMC_DCPD_ADC_OVERFLOW': None,
        'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW': None}


def test_check_vectors_skips_mdc(caplog):
    """Test that detchar checks are skipped for MDC events."""
    caplog.set_level(logging.INFO)
    detchar.check_vectors({'search': 'MDC', 'graceid': 'M1234'}, 'S123', 0, 1)
    messages = [record.message for record in caplog.records]
    assert 'Skipping detchar checks because M1234 is an MDC' in messages


def test_check_vectors_skips_ew(caplog):
    """Test that detchar checks are skipped for events in the future."""
    caplog.set_level(logging.INFO)
    detchar.check_vectors({'pipeline': 'gstlal', 'graceid': 'S1234'},
                          'S123', 99999999999999999, 99999999999999999.5)
    messages = [record.message for record in caplog.records]
    assert 'Skipping detchar checks because S1234 is in the future' in messages  # noqa: E501


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.remove_label')
@patch('gwcelery.tasks.gracedb.create_label')
def test_check_vectors(mock_create_label, mock_remove_label, mock_upload,
                       mock_json, llhoft_glob_pass, ifo_h1, ifo_h1_idq):
    event = {'search': 'AllSky', 'instruments': 'H1', 'pipeline': 'oLIB'}
    superevent_id = 'S12345a'
    start, end = 1216577978, 1216577978.1
    detchar.check_vectors(event, superevent_id, start, end)
    calls = [
        call(
            None, None, 'S12345a',
            ('Detector state for active instruments is good.\n{}'
             'Check looked within -1.5/+1.5 seconds of superevent. ').format(
                 detchar.generate_table(
                     'Data quality bits',
                     ['H1:NO_OMC_DCPD_ADC_OVERFLOW',
                      'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW',
                      'H1:HOFT_OK', 'H1:OBSERVATION_INTENT'], [], [])),
            ['data_quality']),
        call(
            None, None, 'S12345a',
            ('No HW injections found. '
             'Check looked within -1.5/+1.5 seconds of superevent. '),
            ['data_quality']),
        call(
            None, None, 'S12345a',
            ('iDQ glitch probabilities at both H1 and L1'
             ' are good (below {} threshold). '
             'Maximum p(glitch) is "H1:IDQ-PGLITCH_OVL_32_2048": 0.0. '
             'Check looked within -1.5/+1.5 seconds of superevent. ').format(
                 app.conf['idq_pglitch_thresh']),
            ['data_quality']),
        call(
            '"dqrjson"', 'gwcelerydetcharcheckvectors-S12345a.json', 'S12345a',
            'DQR-compatible json generated from check_vectors results'),
    ]
    mock_upload.assert_has_calls(calls, any_order=True)
    mock_create_label.assert_called_with('DQOK', 'S12345a')
    mock_remove_label.assert_has_calls(
        [call('DQV', 'S12345a'),
         call('INJ', 'S12345a')],
        any_order=True)


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.remove_label')
@patch('gwcelery.tasks.gracedb.create_label')
def test_gatedhoft_skips_dmtvec(mock_create_label, mock_remove_label,
                                mock_upload, mock_json, llhoft_glob_pass,
                                ifo_h1, ifo_h1_idq, gatedpipe,
                                gatedpipe_prepost):
    event = {'search': 'AllSky', 'instruments': 'H1', 'pipeline': 'gatepipe'}
    superevent_id = 'S12345a'
    start, end = 1216577977, 1216577979
    detchar.check_vectors(event, superevent_id, start, end)
    mock_upload.assert_has_calls([
            call(None, None, 'S12345a',
                 ('Detector state for active instruments is good.\n{}'
                  'Check looked within -0.5/+0.5 seconds of superevent. '
                  'Pipeline gatepipe uses gated h(t), '
                  'LIGO DMT-DQ_VECTOR not checked.').format(
                      detchar.generate_table(
                          'Data quality bits',
                          ['H1:HOFT_OK', 'H1:OBSERVATION_INTENT'], [], [])),
                 ['data_quality']), ], any_order=True)
    mock_remove_label.assert_has_calls(
        [call('DQV', superevent_id),
         call('INJ', superevent_id)],
        any_order=True)
    mock_create_label.assert_called_once_with('DQOK', superevent_id)


def test_detchar_generate_table():
    result = ('<table '
              'style="width:100%;border-collapse:collapse;text-align:center;"'
              ' border="1">\n<th'
              ' colspan="2">title</th>\n<tr><th>Bit</th><th>Value</th></tr>\n'
              '    <tr><td>good_bit_1</td><td bgcolor="#0f0">1</td></tr>\n'
              '    <tr><td>good_bit_2</td><td bgcolor="#0f0">1</td></tr>\n'
              '    <tr><td>bad_bit_1</td><td bgcolor="red">0</td></tr>\n'
              '    <tr><td>bad_bit_2</td><td bgcolor="red">0</td></tr>\n'
              '    <tr><td>unknown_bit_1</td>'
              '<td bgcolor="yellow">unknown</td></tr>\n'
              '    <tr><td>unknown_bit_2</td>'
              '<td bgcolor="yellow">unknown</td></tr>\n'
              '    <tr bgcolor="red"><th>Overall state for all '
              'detectors</th><th>bad</th></tr>\n'
              '</table>')
    assert detchar.generate_table(
        'title', ['good_bit_1', 'good_bit_2'],
        ['bad_bit_1', 'bad_bit_2'], ['unknown_bit_1', 'unknown_bit_2']
    ) == result
