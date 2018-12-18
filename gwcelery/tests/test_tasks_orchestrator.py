import os
import json
from unittest.mock import Mock, patch

from ligo.gracedb import rest
import pkg_resources
import pytest

from .. import app
from ..tasks import orchestrator
from .test_tasks_skymaps import toy_3d_fits_filecontents  # noqa: F401
from . import resource_json


@pytest.mark.parametrize(  # noqa: F811
    'group,pipeline,offline,far', [['CBC', 'gstlal', False, 1.e-9],
                                   ['CBC', 'gstlal', False, 0.5*app.conf[
                                    'preliminary_alert_far_threshold']],
                                   ['Burst', 'CWB', False, 1.e-9],
                                   ['Burst', 'CWB', False, 0.8*app.conf[
                                    'preliminary_alert_far_threshold']],
                                   ['Burst', 'oLIB', False, 1.e-9],
                                   ['CBC', 'gstlal', True, 1.e-10],
                                   ['Burst', 'CWB', True, 1.e-10]])
def test_handle_superevent(monkeypatch, toy_3d_fits_filecontents,
                           group, pipeline, offline, far):
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
        return {'group': group, 'pipeline': pipeline, 'search': 'AllSky',
                'instruments': 'H1,L1,V1', 'graceid': 'G1234',
                'offline': offline, 'far': far}

    def download(filename, graceid):
        if '.fits' in filename:
            return toy_3d_fits_filecontents
        elif filename == 'source_classification.json' and group == 'CBC':
            return json.dumps({'Prob NS2': 0, 'Prob EMbright': 0})
        elif filename == 'psd.xml.gz':
            return pkg_resources.resource_filename(__name__, 'data/psd.xml.gz')
        elif filename == 'S1234-1-Preliminary.xml':
            return b'fake VOEvent file contents'
        elif filename == 'p_astro.json':
            return json.dumps(dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terr=0.01))
        else:
            raise ValueError

    create_circular = Mock()
    expose = Mock()
    plot_volume = Mock()
    plot_allsky = Mock()
    send = Mock()
    lalinference = Mock()
    create_voevent = Mock(return_value='S1234-1-Preliminary.xml')

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
    monkeypatch.setattr('gwcelery.tasks.lalinference.lalinference.run',
                        lalinference)

    # Run function under test
    orchestrator.handle_superevent(alert)

    expose.assert_not_called()  # FIXME: after ER13, this should be called
    plot_allsky.assert_called_once()
    plot_volume.assert_called_once()
    if offline:
        send.assert_not_called()
        create_circular.assert_not_called()
        lalinference.assert_not_called()
    elif app.conf['preliminary_alert_trials_factor'][group.lower()] * far > \
            app.conf['preliminary_alert_far_threshold']:
        send.assert_not_called()
        create_circular.assert_not_called()
        lalinference.assert_not_called()
    else:
        if group == 'CBC':
            lalinference.assert_called_once()
            create_voevent.assert_called_once_with(
                'S1234', 'preliminary', BBH=0.02, BNS=0.94, NSBH=0.03,
                ProbHasNS=0.0, ProbHasRemnant=0.0, Terrestrial=0.01,
                internal=True, open_alert=True,
                skymap_filename='bayestar.fits.gz',
                skymap_image_filename='bayestar.png', skymap_type='bayestar')
        else:
            lalinference.assert_not_called()
        send.assert_called_once()
        create_circular.assert_called_once()


@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[
        {'self': 'https://gracedb.ligo.org/api/superevents/S181215h/logs/1/',
         'comment': 'Superevent created',
         'created': '2018-12-15 11:10:02 UTC',
         'issuer': 'emfollow'},
        {'self': 'https://gracedb.ligo.org/api/superevents/S181215h/logs/7/',
         'comment': 'Added event: G323163',
         'created': '2018-12-15 11:10:06 UTC',
         'issuer': 'emfollow'},
        {'self': 'https://gracedb.ligo.org/api/superevents/S181215h/logs/84/',
         'comment': 'Added event: G123456',
         'created': '2018-12-15 11:13:04 UTC',
         'issuer': 'emfollow'}])
@patch('gwcelery.tasks.gracedb.get_labels',
       return_value={'DQV', 'ADVREQ'})
def test_handle_superevent_event_added(mock_get_labels, mock_get_log):
    alert = {
        'alert_type': 'event_added',
        'uid': 'TS123456a',
        'data': {'superevent_id': 'TS123456a',
                 't_start': 1.,
                 't_0': 2.,
                 't_end': 3.},
        'object': {'superevent_id': 'TS123456a',
                   't_start': 1.,
                   't_0': 2.,
                   't_end': 3.}
    }
    with patch('gwcelery.tasks.detchar.check_vectors.run') as p:
        orchestrator.handle_superevent(alert)
        p.assert_called_once_with('G123456', 'TS123456a', 1., 3.)


def superevent_initial_alert_download(filename, graceid):
    if filename == 'S1234-Initial-1.xml':
        return 'contents of S1234-Initial-1.xml'
    elif filename == 'source_classification.json':
        return json.dumps({'Prob NS2': 0, 'Prob EMbright': 0})
    elif filename == 'p_astro.json':
        return json.dumps(dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terr=0.01))
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'tag_names': ['sky_loc', 'public'],
                      'filename': 'foobar.fits.gz'}])
@patch('gwcelery.tasks.gracedb.create_tag.run')
@patch('gwcelery.tasks.gracedb.create_voevent.run',
       return_value='S1234-Initial-1.xml')
@patch('gwcelery.tasks.gracedb.expose.run')
@patch('gwcelery.tasks.gracedb.download.run',
       superevent_initial_alert_download)
@patch('gwcelery.tasks.gcn.send.run')
def test_handle_superevent_initial_alert(mock_send, mock_expose,
                                         mock_create_voevent, mock_create_tag,
                                         mock_get_log):
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
        'S1234', 'initial', BBH=0.02, BNS=0.94, NSBH=0.03, ProbHasNS=0.0,
        ProbHasRemnant=0.0, Terrestrial=0.01, internal=False, open_alert=True,
        skymap_filename='foobar.fits.gz', skymap_image_filename='foobar.png',
        skymap_type='foobar', vetted=True)
    mock_send.assert_called_once_with('contents of S1234-Initial-1.xml')
    mock_create_tag.assert_called_once_with(
        'S1234-Initial-1.xml', 'public', 'S1234')


def mock_download(filename, graceid, *args, **kwargs):
    assert graceid == 'T250822'
    filenames = {'coinc.xml': 'coinc.xml',
                 'psd.xml.gz': 'psd.xml.gz',
                 'ranking_data.xml.gz': 'ranking_data_G322589.xml.gz'}
    return pkg_resources.resource_string(
        __name__, os.path.join('data', filenames[filename]))


@patch(
    'gwcelery.tasks.gracedb.get_event.run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal',
                  'far': 1e-7,
                  'extra_attributes':
                      {'CoincInspiral': {'snr': 10.},
                       'SingleInspiral': [{'mass1': 10., 'mass2': 5.}]}})
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


@patch(
    'gwcelery.tasks.gracedb.get_event.run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal',
                  'far': 1e-7,
                  'extra_attributes':
                      {'CoincInspiral': {'snr': 10.},
                       'SingleInspiral': [{'mass1': 10., 'mass2': 5.}]}})
@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier.run')
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event_ignored(mock_gracedb, mock_localize,
                                  mock_classifier,
                                  mock_get_event):
    """Test that unrelated LVAlert messages do not trigger BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_detchar.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_not_called()
    mock_classifier.assert_not_called()
