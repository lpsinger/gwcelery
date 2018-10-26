import os
import json
from unittest.mock import Mock, patch

from ligo.gracedb import rest
import pkg_resources
import pytest

from ..tasks import orchestrator
from . import test_tasks_skymaps
from . import resource_json


@pytest.mark.parametrize(
    'group,pipeline,offline', [['CBC', 'gstlal', False],
                               ['Burst', 'CWB', False],
                               ['Burst', 'oLIB', False],
                               ['CBC', 'gstlal', True],
                               ['Burst', 'CWB', True]])
def test_handle_superevent(monkeypatch, group, pipeline, offline):
    """Test a superevent is dispatched to the correct annotation task based on
    its preferred event's search group."""
    alert = {
        'alert_type': 'new',
        'uid': 'S1234',
        'object': {
            'superevent_id': 'S1234',
            't_start': 1214714160,
            't_end': 1214714164,
            'preferred_event': 'G1234'
        }
    }

    def get_superevent(superevent_id):
        assert superevent_id == 'S1234'
        return {'preferred_event': 'G1234'}

    def get_event(graceid):
        assert graceid == 'G1234'
        return {'group': group, 'pipeline': pipeline,
                'instruments': 'H1,L1,V1', 'graceid': 'G1234',
                'offline': offline}

    def download(filename, graceid):
        if '.fits' in filename:
            return test_tasks_skymaps.toy_3d_fits_filecontents()
        elif filename == 'source_classification.json' and group == 'CBC':
            return json.dumps({'Prob NS2': 0, 'Prob EMbright': 0})
        elif filename == 'psd.xml.gz':
            return pkg_resources.resource_filename(__name__, 'data/psd.xml.gz')
        elif filename == 'S1234-1-Preliminary.xml':
            return b'fake VOEvent file contents'
        else:
            raise ValueError

    def create_voevent(*args, **kwargs):
        return 'S1234-1-Preliminary.xml'

    create_circular = Mock()
    expose = Mock()
    plot_volume = Mock()
    plot_allsky = Mock()
    send = Mock()

    monkeypatch.setattr('gwcelery.tasks.gcn.send.run', send)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_allsky.run', plot_allsky)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_volume.run', plot_volume)
    monkeypatch.setattr('gwcelery.tasks.gracedb.download.run', download)
    monkeypatch.setattr('gwcelery.tasks.gracedb.expose.run', expose)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_event.run', get_event)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_voevent.run',
                        create_voevent)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_superevent.run',
                        get_superevent)
    monkeypatch.setattr('gwcelery.tasks.circulars.create_circular.run',
                        create_circular)

    # Run function under test
    orchestrator.handle_superevent(alert)

    expose.assert_called_once()
    plot_allsky.assert_called_once()
    plot_volume.assert_called_once()
    if not offline:
        send.assert_called_once()
        create_circular.assert_called_once()
    else:
        send.assert_not_called()
        create_circular.assert_not_called()


@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'tag_names': ['sky_loc', 'public'],
                      'filename': 'foobar.fits.gz'}])
@patch('gwcelery.tasks.gracedb.create_voevent.run',
       return_value='S1234-Initial-1.xml')
@patch('gwcelery.tasks.gracedb.expose.run')
@patch('gwcelery.tasks.gracedb.download.run',
       return_value='contents of S1234-Initial-1.xml')
@patch('gwcelery.tasks.gcn.send.run')
def test_handle_superevent_initial_alert(mock_send, mock_download, mock_expose,
                                         mock_create_voevent, mock_get_log):
    """Test that the ``ADVOK`` label triggers an initial alert."""
    alert = {
        'alert_type': 'label_added',
        'uid': 'S1234',
        'data': {'name': 'ADVOK'}
    }

    # Run function under test
    orchestrator.handle_superevent(alert)

    mock_expose.assert_called_once_with('S1234')
    mock_create_voevent.assert_called_once_with(
        'S1234', 'initial', skymap_filename='foobar.fits.gz',
        skymap_image_filename='foobar.png', skymap_type='foobar', vetted=True)
    mock_send.assert_called_once_with('contents of S1234-Initial-1.xml')


def mock_download(filename, graceid, *args, **kwargs):
    assert graceid == 'T250822'
    filenames = {'coinc.xml': 'coinc.xml',
                 'psd.xml.gz': 'psd.xml.gz',
                 'ranking_data.xml.gz': 'ranking_data_G322589.xml.gz'}
    return pkg_resources.resource_string(
        __name__, os.path.join('data', filenames[filename]))


@patch(
    'gwcelery.tasks.gracedb.get_event.run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal'})
@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier.run')
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event(mock_gracedb, mock_localize, mock_classifier,
                          mock_get_event):
    """Test that an LVAlert message for a newly uploaded PSD file triggers
    BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_psd.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_called_once()
    mock_classifier.assert_called_once()


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier.run')
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event_ignored(mock_gracedb, mock_localize,
                                  mock_classifier):
    """Test that unrelated LVAlert messages do not trigger BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_detchar.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_not_called()
    mock_classifier.assert_not_called()
