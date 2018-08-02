from unittest.mock import patch

from pkg_resources import resource_string

from ..tasks.gcn import external_triggers


@patch('gwcelery.tasks.gracedb.create_label')
@patch('gwcelery.tasks.gracedb.client.writeLog')
@patch('gwcelery.tasks.gracedb.get_event', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'extra_attributes': {'GRB': {'trigger_duration': 1}}})
@patch('gwcelery.tasks.gracedb.create_event')
def test_handle_create_event(mock_create_event, mock_get_event, mock_write_log,
                             mock_create_label):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External')
    mock_write_log.assert_called_with(
        'E1',
        ('detector state for active instruments is unknown. For all'
         ' instruments, bits good (), bad (),'
         ' unknown(H1:NO_OMC_DCPD_ADC_OVERFLOW,'
         ' H1:NO_DMT-ETMY_ESD_DAC_OVERFLOW, L1:NO_OMC_DCPD_ADC_OVERFLOW,'
         ' L1:NO_DMT-ETMY_ESD_DAC_OVERFLOW, H1:HOFT_OK, H1:OBSERVATION_INTENT,'
         ' L1:HOFT_OK, L1:OBSERVATION_INTENT, V1:HOFT_OK,'
         ' V1:OBSERVATION_INTENT, V1:NO_DQ_VETO_MBTA, V1:NO_DQ_VETO_CWB,'
         ' V1:NO_DQ_VETO_GSTLAL, V1:NO_DQ_VETO_OLIB, V1:NO_DQ_VETO_PYCBC).'),
        tag_name=['data_quality'])


@patch('gwcelery.tasks.gracedb.replace_event')
@patch('gwcelery.tasks.gracedb.get_events', return_value=[{'graceid': 'E1'}])
def test_handle_replace_event(mock_get_events, mock_replace_event):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle(payload=text)
    mock_replace_event.assert_called_once_with('E1', text)
