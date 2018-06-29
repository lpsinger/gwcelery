from unittest.mock import patch

from pkg_resources import resource_string

from ..tasks.gcn import external_triggers


@patch('gwcelery.tasks.gracedb.create_event')
def test_handle_create_event(mock_create_event):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='External')


@patch('gwcelery.tasks.gracedb.get_events', return_value=[{'graceid': 'E1'}])
@patch('gwcelery.tasks.gracedb.replace_event')
def test_handle_replace_event(mock_replace_event, mock_get_events):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    external_triggers.handle(payload=text)
    mock_replace_event.assert_called_once_with('E1', text)
