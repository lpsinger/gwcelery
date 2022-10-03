from importlib.resources import read_binary
from unittest.mock import patch, call

import pytest

from . import data
from ..tasks import external_triggers
from ..tasks import detchar
from ..util import read_json


@pytest.mark.parametrize('pipeline, path',
                         [['Fermi', 'fermi_grb_gcn.xml'],
                          ['INTEGRAL', 'integral_grb_gcn.xml'],
                          ['AGILE', 'agile_grb_gcn.xml']])
@patch('gwcelery.tasks.external_skymaps.create_upload_external_skymap.run')
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.create_event.run', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'GRB',
    'extra_attributes': {'GRB': {'trigger_duration': 1, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 10.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}})
def test_handle_create_grb_event(mock_create_event,
                                 mock_upload, mock_json,
                                 mock_get_upload_external_skymap,
                                 mock_create_upload_external_skymap,
                                 pipeline, path):
    text = read_binary(data, path)
    external_triggers.handle_grb_gcn(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline=pipeline,
                                              group='External',
                                              labels=None)
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
    gcn_type_dict = {'Fermi': 115, 'INTEGRAL': 53, 'AGILE': 105}
    time_dict = {'Fermi': '2018-05-24T18:35:45',
                 'INTEGRAL': '2017-02-03T19:00:05',
                 'AGILE': '2019-03-19T19:40:49'}
    mock_create_upload_external_skymap.assert_called_once_with(
        {'graceid': 'E1',
         'gpstime': 1,
         'instruments': '',
         'pipeline': 'Fermi',
         'search': 'GRB',
         'extra_attributes': {
             'GRB': {
                 'trigger_duration': 1,
                 'trigger_id': 123,
                 'ra': 0.0,
                 'dec': 0.0,
                 'error_radius': 10.0
                    }
              },
         'links': {
             'self': 'https://gracedb.ligo.org/events/E356793/'
                  }
         },
        gcn_type_dict[pipeline], time_dict[pipeline])


@patch('gwcelery.tasks.gracedb.get_events', return_value=[])
@patch('gwcelery.tasks.gracedb.create_event.run', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'SubGRB',
    'extra_attributes': {'GRB': {'trigger_duration': None, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 10.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}})
@patch('gwcelery.tasks.detchar.check_vectors.run')
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
def test_handle_create_subthreshold_grb_event(mock_get_upload_ext_skymap,
                                              mock_check_vectors,
                                              mock_create_event,
                                              mock_get_events):
    text = read_binary(data, 'fermi_subthresh_grb_lowconfidence.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_create_event.assert_not_called()
    text = read_binary(data, 'fermi_subthresh_grb_gcn.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_get_events.assert_called_once_with(query=(
                                            'group: External pipeline: '
                                            'Fermi grbevent.trigger_id '
                                            '= "578679123"'))
    # Note that this is the exact ID in the .xml file
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='SubGRB',
                                              pipeline='Fermi',
                                              group='External',
                                              labels=None)
    mock_check_vectors.assert_called_once()
    mock_get_upload_ext_skymap.assert_called_with(
        {'graceid': 'E1', 'gpstime': 1, 'instruments': '',
         'pipeline': 'Fermi', 'search': 'SubGRB',
         'extra_attributes': {
             'GRB': {'trigger_duration': None, 'trigger_id': 123,
                     'ra': 0., 'dec': 0., 'error_radius': 10.}},
         'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}},
        ('https://gcn.gsfc.nasa.gov/notices_gbm_sub/' +
         'gbm_subthresh_578679393.215999_healpix.fits'))


@pytest.mark.parametrize('filename',
                         ['fermi_noise_gcn.xml',
                          'fermi_noise_gcn_2.xml'])
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[])
@patch('gwcelery.tasks.gracedb.create_event.run', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'GRB',
    'extra_attributes': {'GRB': {'trigger_duration': 1, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 10.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}})
@patch('gwcelery.tasks.detchar.check_vectors.run')
def test_handle_noise_fermi_event(mock_check_vectors,
                                  mock_create_event,
                                  mock_get_events,
                                  mock_get_upload_external_skymap,
                                  filename):
    text = read_binary(data, filename)
    external_triggers.handle_grb_gcn(payload=text)
    mock_get_events.assert_called_once_with(query=(
                                            'group: External pipeline: '
                                            'Fermi grbevent.trigger_id '
                                            '= "598032876"'))
    # Note that this is the exact ID in the .xml file
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External',
                                              labels=['NOT_GRB'])
    mock_check_vectors.assert_called_once()
    mock_get_upload_external_skymap.assert_called_once()


@patch('gwcelery.tasks.external_skymaps.create_external_skymap')
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[])
@patch('gwcelery.tasks.gracedb.create_event.run', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'GRB',
    'extra_attributes': {'GRB': {'trigger_duration': 1, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 0.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}})
@patch('gwcelery.tasks.detchar.check_vectors.run')
def test_handle_initial_fermi_event(mock_check_vectors,
                                    mock_create_event,
                                    mock_get_events,
                                    mock_get_upload_external_skymap,
                                    mock_create_external_skymap):
    text = read_binary(data, 'fermi_initial_grb_gcn.xml')
    external_triggers.handle_grb_gcn(payload=text)
    mock_get_events.assert_called_once_with(query=(
                                            'group: External pipeline: '
                                            'Fermi grbevent.trigger_id '
                                            '= "548841234"'))
    # Note that this is the exact ID in the .xml file
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External',
                                              labels=['NOT_GRB'])
    mock_check_vectors.assert_called_once()
    mock_get_upload_external_skymap.assert_called_once()
    mock_create_external_skymap.assert_not_called()


@pytest.mark.parametrize('filename',
                         ['fermi_grb_gcn.xml',
                          'fermi_noise_gcn.xml',
                          'fermi_subthresh_grb_gcn.xml'])
@patch('gwcelery.tasks.external_skymaps.create_upload_external_skymap.run')
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
@patch('gwcelery.tasks.gracedb.create_label.run')
@patch('gwcelery.tasks.gracedb.remove_label.run')
@patch('gwcelery.tasks.gracedb.replace_event.run')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[{
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'GRB',
    'extra_attributes': {'GRB': {'trigger_duration': 1, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 10.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}}])
def test_handle_replace_grb_event(mock_get_events,
                                  mock_replace_event, mock_remove_label,
                                  mock_create_label,
                                  mock_get_upload_external_skymap,
                                  mock_create_upload_external_skymap,
                                  filename):
    text = read_binary(data, filename)
    external_triggers.handle_grb_gcn(payload=text)
    if 'subthresh' in filename:
        mock_replace_event.assert_not_called()
        mock_remove_label.assert_not_called()
        mock_create_label.assert_not_called()
    elif 'grb' in filename:
        mock_replace_event.assert_called_once_with('E1', text)
        mock_remove_label.assert_called_once_with('NOT_GRB', 'E1')
    elif 'noise' in filename:
        mock_replace_event.assert_called_once_with('E1', text)
        mock_create_label.assert_called_once_with('NOT_GRB', 'E1')


@patch('gwcelery.tasks.gracedb.get_group', return_value='CBC')
@patch('gwcelery.tasks.gracedb.create_label.run')
@patch('gwcelery.tasks.gracedb.get_labels',
       return_value=['SKYMAP_READY'])
def test_handle_create_skymap_label_from_ext_event(mock_get_labels,
                                                   mock_create_label,
                                                   mock_get_group):
    alert = {"uid": "E1212",
             "alert_type": "label_added",
             "data": {"name": "EM_COINC"},
             "object": {
                 "group": "External",
                 "labels": ["EM_COINC", "EXT_SKYMAP_READY"],
                 "superevent": "S1234"
                       }
             }
    external_triggers.handle_grb_igwn_alert(alert)
    mock_create_label.assert_called_once_with('SKYMAP_READY', 'E1212')


@patch('gwcelery.tasks.gracedb.get_group', return_value='CBC')
@patch('gwcelery.tasks.gracedb.create_label.run')
def test_handle_create_skymap_label_from_superevent(mock_create_label,
                                                    mock_get_group):
    alert = {"uid": "S1234",
             "alert_type": "label_added",
             "data": {"name": "SKYMAP_READY"},
             "object": {
                 "group": "CBC",
                 "labels": ["SKYMAP_READY"],
                 "superevent_id": "S1234",
                 "em_events": ['E1212']
                       }
             }
    external_triggers.handle_grb_igwn_alert(alert)
    mock_create_label.assert_called_once_with('SKYMAP_READY', 'E1212')


@patch('gwcelery.tasks.gracedb.get_group', return_value='CBC')
@patch('gwcelery.tasks.raven.raven_pipeline')
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={
           'superevent_id': 'S1234',
           'preferred_event': 'G1234'
                    })
@patch('gwcelery.tasks.gracedb.get_event',
       return_value={
           'graceid': 'G1234',
           'group': 'CBC'
                    })
def test_handle_skymap_comparison(mock_get_event, mock_get_superevent,
                                  mock_raven_pipeline, mock_get_group):
    alert = {"uid": "E1212",
             "alert_type": "label_added",
             "data": {"name": "SKYMAP_READY"},
             "object": {
                 "graceid": "E1212",
                 "group": "External",
                 "labels": ["EM_COINC", "EXT_SKYMAP_READY", "SKYMAP_READY"],
                 "superevent": "S1234",
                 "pipeline": "Fermi",
                 "search": "GRB"
                       }
             }
    external_triggers.handle_grb_igwn_alert(alert)
    mock_raven_pipeline.assert_called_once_with([alert['object']], 'S1234',
                                                {'superevent_id': 'S1234',
                                                 'preferred_event': 'G1234'},
                                                -5, 1, 'CBC')


@patch('gwcelery.tasks.raven.trigger_raven_alert')
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'superevent_id': 'S1234',
                     'preferred_event': 'G1234',
                     'preferred_event_data': {
                         'group': 'CBC'},
                     'time_coinc_far': 1e-9,
                     'space_coinc_far': 1e-10})
def test_handle_label_removed(mock_get_superevent,
                              mock_trigger_raven_alert):
    alert = {"uid": "E1212",
             "alert_type": "label_removed",
             "data": {"name": "NOT_GRB"},
             "object": {
                 "graceid": "E1212",
                 "group": "External",
                 "labels": ["EM_COINC", "EXT_SKYMAP_READY", "SKYMAP_READY"],
                 "superevent": "S1234",
                 "pipeline": "Fermi",
                 "search": "GRB"
                       }
             }
    superevent = {'superevent_id': 'S1234',
                  'preferred_event': 'G1234',
                  'preferred_event_data': {
                      'group': 'CBC'},
                  'time_coinc_far': 1e-9,
                  'space_coinc_far': 1e-10}
    coinc_far_dict = {
                'temporal_coinc_far': 1e-9,
                'spatiotemporal_coinc_far': 1e-10
            }
    external_triggers.handle_grb_igwn_alert(alert)
    mock_trigger_raven_alert.assert_called_once_with(
        coinc_far_dict, superevent, alert['uid'],
        alert['object'], 'CBC'
    )


@patch('gwcelery.tasks.external_skymaps.create_combined_skymap')
def test_handle_skymap_combine(mock_create_combined_skymap):
    alert = {"uid": "E1212",
             "alert_type": "label_added",
             "data": {"name": "RAVEN_ALERT"},
             "object": {
                 "graceid": "E1212",
                 "group": "External",
                 "labels": ["EM_COINC", "EXT_SKYMAP_READY", "SKYMAP_READY",
                            "RAVEN_ALERT"],
                 "superevent": "S1234"}
             }
    external_triggers.handle_grb_igwn_alert(alert)
    mock_create_combined_skymap.assert_called_once_with('S1234', 'E1212')


@patch('gwcelery.tasks.detchar.dqr_json', return_value='dqrjson')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.gracedb.get_event', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'SNEWS'})
@patch('gwcelery.tasks.gracedb.create_event')
def test_handle_create_snews_event(mock_create_event, mock_get_event,
                                   mock_upload, mock_json):
    text = read_binary(data, 'snews_gcn.xml')
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
    text = read_binary(data, 'snews_gcn.xml')
    external_triggers.handle_snews_gcn(payload=text)
    mock_replace_event.assert_called_once_with('E1', text)


@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_grb_exttrig_creation(mock_raven_coincidence_search):
    """Test dispatch of an IGWN alert message for an exttrig creation."""
    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_exttrig_creation.json')

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('E1234', alert['object'], group='Burst', se_searches=['Allsky']),
        call('E1234', alert['object'], group='CBC', searches=['GRB'])])


@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_subgrb_exttrig_creation(mock_raven_coincidence_search):
    """Test dispatch of an IGWN alert message for an exttrig creation."""
    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_subgrb_creation.json')

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('E1234', alert['object'], group='Burst', se_searches=['Allsky']),
        call('E1234', alert['object'], group='CBC',
             searches=['SubGRB', 'SubGRBTargeted'], pipelines=['Fermi'])])


@patch('gwcelery.tasks.external_skymaps.create_upload_external_skymap')
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_subgrb_targeted_creation(mock_raven_coincidence_search,
                                         mock_create_upload_external_skymap):
    """Test dispatch of an IGWN alert message for an exttrig creation."""
    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_exttrig_subgrb_targeted_creation.json')

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that sky map is uploaded
    mock_create_upload_external_skymap.assert_called_once_with(
        alert['object'], None, alert['object']['created'])

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('E1234', alert['object'], group='Burst', se_searches=['Allsky']),
        call('E1234', alert['object'], group='CBC',
             searches=['SubGRB', 'SubGRBTargeted'],
             pipelines=['Swift'])])


@pytest.mark.parametrize('path',
                         ['igwn_alert_snews_test_creation.json',
                          'igwn_alert_snews_creation.json'])
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_sntrig_creation(mock_raven_coincidence_search, path):
    """Test dispatch of an IGWN alert message for SNEWS alerts
    This now includes both real and test SNEWS events to ensure both are
    ingested correctly.
    """
    # Test IGWN alert payload.
    alert = read_json(data, path)

    # Run function under test
    external_triggers.handle_snews_igwn_alert(alert)

    if 'test' in path:
        graceid = 'E1236'
    else:
        graceid = 'E1235'

    mock_raven_coincidence_search.assert_has_calls([
            call(graceid, alert['object'],
                 group='Burst', searches=['Supernova'],
                 pipelines=['SNEWS'])])


@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'preferred_event': 'M4634'})
@patch('gwcelery.tasks.gracedb.get_group', return_value='CBC')
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_superevent_cbc_creation(mock_raven_coincidence_search,
                                        mock_get_group,
                                        mock_get_superevent):
    """Test dispatch of an IGWN alert message for a CBC superevent creation."""
    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_superevent_creation.json')

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('S180616h', alert['object'], group='CBC',
             pipelines=['Fermi'], searches=['SubGRB', 'SubGRBTargeted']),
        call('S180616h', alert['object'], group='CBC',
             pipelines=['Swift'], searches=['SubGRB', 'SubGRBTargeted']),
        call('S180616h', alert['object'], group='CBC',
             searches=['GRB'], se_searches=[])])


@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'preferred_event': 'M4634'})
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_superevent_burst_creation(mock_raven_coincidence_search,
                                          mock_get_superevent):
    """
    Test dispatch of an IGWN alert message for a burst superevent
    creation.
    """
    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_superevent_creation.json')
    alert['object']['preferred_event_data']['group'] = 'Burst'

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_has_calls([
        call('S180616h', alert['object'], group='Burst', searches=['GRB'],
             se_searches=['Allsky'])])


@pytest.mark.parametrize('path',
                         ['igwn_alert_superevent_creation.json',
                          'igwn_alert_exttrig_creation.json'])
@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_mdc_creation(mock_raven_coincidence_search,
                             path):
    """Test dispatch of an IGWN alert message for a CBC superevent creation."""
    # Test IGWN alert payload.
    alert = read_json(data, path)
    if 'superevent' in path:
        alert['object']['preferred_event_data']['search'] = 'MDC'
    elif 'exttrig' in path:
        alert['object']['search'] = 'MDC'

    # Run function under test
    external_triggers.handle_grb_igwn_alert(alert)

    # Check that the correct tasks were dispatched.
    if 'superevent' in path:
        calls = [call('S180616h', alert['object'], group='CBC',
                      searches=['MDC'])]
    elif 'exttrig' in path:
        calls = [call('E1234', alert['object'], group='CBC',
                      se_searches=['MDC']),
                 call('E1234', alert['object'], group='Burst',
                      se_searches=['MDC'])]
    mock_raven_coincidence_search.assert_has_calls(calls, any_order=True)
