from unittest.mock import patch, call

import pytest

from pkg_resources import resource_string

from ..tasks import external_triggers
from ..tasks import detchar
from . import resource_json


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.get_event', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'extra_attributes': {'GRB': {'trigger_duration': 1}}})
@patch('gwcelery.tasks.gracedb.create_event')
def test_handle_create_grb_event(mock_create_event, mock_get_event,
                                 mock_upload, mock_json):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External')
    calls = [
        call(
            '"dqrjson"', 'gwcelerydetcharcheckvectors-E1.json', 'E1',
            'DQR-compatible json generated from check_vectors results'),
        call(
            None, None, 'E1',
            ('Detector state for active instruments is unknown.\n{}'
             'Check looked within -2/+2 seconds of superevent. ').format(
                 detchar.generate_table(
                     'Data quality bits', [], [],
                     ['H1:NO_OMC_DCPD_ADC_OVERFLOW',
                      'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW',
                      'L1:NO_OMC_DCPD_ADC_OVERFLOW',
                      'L1:NO_DMT-ETMY_ESD_DAC_OVERFLOW',
                      'H1:HOFT_OK', 'H1:OBSERVATION_INTENT',
                      'L1:HOFT_OK', 'L1:OBSERVATION_INTENT',
                      'V1:HOFT_OK', 'V1:OBSERVATION_INTENT',
                      'V1:GOOD_DATA_QUALITY_CAT1'])),
            ['data_quality'])
    ]
    mock_upload.assert_has_calls(calls, any_order=True)


@patch('gwcelery.tasks.gracedb.get_events', return_value=[])
@patch('gwcelery.tasks.gracedb.get_event')
@patch('gwcelery.tasks.gracedb.create_event')
@patch('gwcelery.tasks.detchar.check_vectors')
def test_handle_create_subthreshold_grb_event(mock_check_vectors,
                                              mock_create_event,
                                              mock_get_event,
                                              mock_get_events):
    text = resource_string(__name__, 'data/fermi_subthresh_grb_gcn.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_get_events.assert_called_once_with(query=(
                                            'group: External pipeline: '
                                            'Fermi grbevent.trigger_id '
                                            '= "578679123"'))
    # Note that this is the exact ID in the .xml file
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External')
    mock_check_vectors.assert_called_once()


@patch('gwcelery.tasks.gracedb.replace_event')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[{'graceid': 'E1'}])
def test_handle_replace_grb_event(mock_get_events, mock_replace_event):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_replace_event.assert_called_once_with('E1', text)


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.get_event', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'SNEWS'})
@patch('gwcelery.tasks.gracedb.create_event')
def test_handle_create_snews_event(mock_create_event, mock_get_event,
                                   mock_upload, mock_json):
    text = resource_string(__name__, 'data/snews_gcn.xml')
    external_triggers.handle_snews_gcn(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='Supernova',
                                              pipeline='SNEWS',
                                              group='External')
    calls = [
        call(
            '"dqrjson"', 'gwcelerydetcharcheckvectors-E1.json', 'E1',
            'DQR-compatible json generated from check_vectors results'),
        call(
            None, None, 'E1',
            ('Detector state for active instruments is unknown.\n{}'
             'Check looked within -10/+10 seconds of superevent. ').format(
                 detchar.generate_table(
                     'Data quality bits', [], [],
                     ['H1:NO_OMC_DCPD_ADC_OVERFLOW',
                      'H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW',
                      'L1:NO_OMC_DCPD_ADC_OVERFLOW',
                      'L1:NO_DMT-ETMY_ESD_DAC_OVERFLOW',
                      'H1:HOFT_OK', 'H1:OBSERVATION_INTENT',
                      'L1:HOFT_OK', 'L1:OBSERVATION_INTENT',
                      'V1:HOFT_OK', 'V1:OBSERVATION_INTENT',
                      'V1:GOOD_DATA_QUALITY_CAT1'])),
            ['data_quality'])
    ]
    mock_upload.assert_has_calls(calls, any_order=True)


@patch('gwcelery.tasks.gracedb.replace_event')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[{'graceid': 'E1'}])
def test_handle_replace_snews_event(mock_get_events, mock_replace_event):
    text = resource_string(__name__, 'data/snews_gcn.xml')
    external_triggers.handle_snews_gcn(payload=text)
    mock_replace_event.assert_called_once_with('E1', text)


@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_grb_exttrig_creation(mock_raven_coincidence_search):
    """Test dispatch of an LVAlert message for an exttrig creation."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_exttrig_creation.json')

    # Run function under test
    external_triggers.handle_grb_lvalert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('E1234', alert['object'], group='CBC'),
        call('E1234', alert['object'], group='Burst')])


@pytest.mark.parametrize('calls, path',
                         [[False, 'data/lvalert_snews_test_creation.json'],
                          [True, 'data/lvalert_snews_creation.json']])
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_sntrig_creation(mock_raven_coincidence_search, calls, path):
    """Test dispatch of an LVAlert message for SNEWS alerts."""
    # Test LVAlert payload.
    alert = resource_json(__name__, path)

    # Run function under test
    external_triggers.handle_snews_lvalert(alert)

    if calls is True:
        mock_raven_coincidence_search.assert_has_calls([
                call('E1235', alert['object'],
                     group='Burst', pipelines=['SNEWS'])])
    else:
        mock_raven_coincidence_search.assert_not_called()


@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'preferred_event': 'M4634'})
@patch('gwcelery.tasks.gracedb.get_event', return_value={'group': 'CBC'})
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_superevent_creation(mock_raven_coincidence_search,
                                    mock_get_event,
                                    mock_get_superevent):
    """Test dispatch of an LVAlert message for a superevent creation."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_superevent_creation.json')

    # Run function under test
    external_triggers.handle_grb_lvalert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_called_once_with(
        'S180616h', alert['object'], group='CBC',
        pipelines=['Fermi', 'Swift'])


@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'preferred_event': 'M4634'})
@patch('gwcelery.tasks.gracedb.get_event', return_value={'group': 'CBC'})
@patch('gwcelery.tasks.raven.calculate_spacetime_coincidence_far')
@patch('gwcelery.tasks.ligo_fermi_skymaps.create_combined_skymap')
def test_handle_superevent_emcoinc_label1(mock_create_combined_skymap,
                                          mock_calc_spacetime_coinc_far,
                                          mock_get_event, mock_get_superevent,
                                          mock_se_cls, mock_exttrig_cls):
    """Test dispatch of an LVAlert message for a superevent EM_COINC label
    application."""
    alert = resource_json(__name__, 'data/lvalert_superevent_label.json')

    external_triggers.handle_grb_lvalert(alert)
    mock_create_combined_skymap.assert_called_once_with('S180616h')
    mock_calc_spacetime_coinc_far.assert_called_once_with('S180616h',
                                                          'CBC')


@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.circulars.create_emcoinc_circular.run')
def test_handle_superevent_emcoinc_label2(mock_create_emcoinc_circular,
                                          mock_gracedb_upload):
    """Test dispatch of an LVAlert message for a superevent EM_COINC label
    application."""
    alert = resource_json(__name__, 'data/lvalert_superevent_label.json')

    external_triggers.handle_emcoinc_lvalert(alert)
    mock_create_emcoinc_circular.assert_called_once_with('S180616h')
    mock_gracedb_upload.assert_called_once()
