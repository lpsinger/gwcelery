from unittest.mock import call, patch

from . import data
from ..tasks import first2years_external
from ..util import read_json


@patch('gwcelery.tasks.external_skymaps.create_upload_external_skymap.run')
@patch('gwcelery.tasks.external_skymaps.get_upload_external_skymap.run')
@patch('gwcelery.tasks.detchar.check_vectors.run')
@patch('gwcelery.tasks.gracedb.create_event.run', return_value={
    'graceid': 'E1', 'gpstime': 1, 'instruments': '', 'pipeline': 'Fermi',
    'search': 'GRB',
    'extra_attributes': {'GRB': {'trigger_duration': 1, 'trigger_id': 123,
                                 'ra': 0., 'dec': 0., 'error_radius': 10.}},
    'links': {'self': 'https://gracedb.ligo.org/events/E356793/'}})
@patch('gwcelery.tasks.gracedb.get_events', return_value=[])
def test_handle_create_grb_event(mock_get_events,
                                 mock_create_event,
                                 mock_check_vectors,
                                 mock_get_upload_external_skymap,
                                 mock_create_upload_external_skymap):

    # Test IGWN alert payload.
    alert = read_json(data, 'igwn_alert_superevent_creation.json')

    alert['uid'] = 'MS180616j'
    alert['object']['superevent_id'] = alert['uid']
    alert['object']['preferred_event_data']['search'] = 'MDC'
    events, pipelines = first2years_external.upload_external_event(alert)

    calls = []
    for i in range(len(events)):
        calls.append(call(filecontents=events[i],
                          search='MDC',
                          pipeline=pipelines[i],
                          group='External',
                          labels=None))
    mock_create_event.assert_has_calls(calls)
    mock_create_upload_external_skymap.assert_called()
