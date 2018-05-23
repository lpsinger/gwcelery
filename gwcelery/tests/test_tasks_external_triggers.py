from unittest.mock import patch

# import pytest

from pkg_resources import resource_string

from ..tasks.gcn.external_triggers import handle_exttrig


@patch('gwcelery.tasks.gracedb.create_event', return_value='T0446')
@patch('gwcelery.tasks.gracedb.upload')
def test_handle_exttrig(mock_upload, mock_create_event):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    handle_exttrig(payload=text)
    mock_create_event.assert_called_once_with(filecontents=text,
                                              search='GRB',
                                              pipeline='Fermi',
                                              group='Test')
