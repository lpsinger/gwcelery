import os
import json
from unittest.mock import Mock, patch, call

from ligo.gracedb import rest
import pkg_resources
import pytest

from .. import app
from ..tasks import lalinference
from ..tasks import orchestrator
from ..tasks import superevents
from .test_tasks_skymaps import toy_3d_fits_filecontents  # noqa: F401
from . import resource_json


@pytest.mark.parametrize(  # noqa: F811
    'group,pipeline,offline,far,instruments',
    [['CBC', 'gstlal', False, 1.e-9, ['H1']],
     ['CBC', 'gstlal', False, 1.e-9, ['H1', 'L1']],
     ['CBC', 'gstlal', False, 1.e-9, ['H1', 'L1', 'V1']],
     ['CBC', 'gstlal', False, 0.5*app.conf[
      'preliminary_alert_far_threshold']['cbc'], ['H1', 'L1', 'V1']],
     ['Burst', 'CWB', False, 1.e-9, ['H1', 'L1', 'V1']],
     ['Burst', 'CWB', False, 0.8*app.conf[
      'preliminary_alert_far_threshold']['cbc'], ['H1', 'L1', 'V1']],
     ['Burst', 'oLIB', False, 1.e-9, ['H1', 'L1', 'V1']],
     ['CBC', 'gstlal', True, 1.e-10, ['H1', 'L1', 'V1']],
     ['Burst', 'CWB', True, 1.e-10, ['H1', 'L1', 'V1']],
     ['CBC', 'gstlal', False, 2.0*app.conf['pe_threshold'],
      ['H1', 'L1', 'V1']]])
def test_handle_superevent(monkeypatch, toy_3d_fits_filecontents,  # noqa: F811
                           group, pipeline, offline, far, instruments):
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
        return {'preferred_event': 'G1234', 'gw_events': ['G1234']}

    def get_event(graceid):
        assert graceid == 'G1234'
        event = {
            'group': group,
            'pipeline': pipeline,
            'search': 'AllSky',
            'graceid': 'G1234',
            'offline': offline,
            'far': far,
            'gpstime': 1234,
            'extra_attributes': {}
        }
        if pipeline == 'gstlal':
            # Simulate subthreshold triggers for gstlal. Subthreshold triggers
            # do not contribute to the significance estimate. The way that we
            # can tell that a subthreshold trigger is present is that the chisq
            # entry in the SingleInspiral record is empty (``None``).
            event['extra_attributes']['SingleInspiral'] = [
                {'chisq': 1 if instrument in instruments else None}
                for instrument in ['H1', 'L1', 'V1']]
            event['instruments'] = 'H1,L1,V1'
        else:
            event['instruments'] = ','.join(instruments)
        return event

    def download(filename, graceid):
        if '.fits' in filename:
            return toy_3d_fits_filecontents
        elif filename == 'em_bright.json' and group == 'CBC':
            return json.dumps({'HasNS': 0.0, 'HasRemnant': 0.0})
        elif filename == 'psd.xml.gz':
            return pkg_resources.resource_filename(__name__, 'data/psd.xml.gz')
        elif filename == 'S1234-1-Preliminary.xml':
            return b'fake VOEvent file contents'
        elif filename == 'p_astro.json':
            return json.dumps(
                dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terrestrial=0.01))
        elif filename == lalinference.ini_name:
            return 'test'
        else:
            raise ValueError

    create_initial_circular = Mock()
    expose = Mock()
    plot_volume = Mock()
    plot_allsky = Mock()
    send = Mock()
    query_data = Mock()
    prepare_ini = Mock()
    start_pe = Mock()
    create_voevent = Mock(return_value='S1234-1-Preliminary.xml')
    create_label = Mock()
    create_tag = Mock()

    monkeypatch.setattr('gwcelery.tasks.gcn.send.run', send)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_allsky.run', plot_allsky)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_volume.run', plot_volume)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_tag.run', create_tag)
    monkeypatch.setattr('gwcelery.tasks.gracedb.download.run', download)
    monkeypatch.setattr('gwcelery.tasks.gracedb.expose.run', expose)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_event.run', get_event)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_voevent.run',
                        create_voevent)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_superevent.run',
                        get_superevent)
    monkeypatch.setattr('gwcelery.tasks.circulars.create_initial_circular.run',
                        create_initial_circular)
    monkeypatch.setattr('gwcelery.tasks.lalinference.query_data.run',
                        query_data)
    monkeypatch.setattr('gwcelery.tasks.lalinference.prepare_ini.run',
                        prepare_ini)
    monkeypatch.setattr('gwcelery.tasks.lalinference.start_pe.run',
                        start_pe)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_label.run',
                        create_label)

    # Run function under test
    orchestrator.handle_superevent(alert)

    plot_allsky.assert_called_once()
    plot_volume.assert_called_once()

    _event_info = get_event('G1234')    # this gets the preferred event info
    if not superevents.should_publish(_event_info):
        expose.assert_not_called()
        create_tag.assert_not_called()
        send.assert_not_called()
        create_initial_circular.assert_not_called()
        assert call('ADVREQ', 'S1234') not in create_label.call_args_list
    else:
        expose.assert_called_once_with('S1234')
        create_tag.assert_called_once_with(
            'S1234-1-Preliminary.xml', 'public', 'S1234')
        if group == 'CBC':
            create_voevent.assert_called_once_with(
                'S1234', 'preliminary', BBH=0.02, BNS=0.94, NSBH=0.03,
                ProbHasNS=0.0, ProbHasRemnant=0.0, Terrestrial=0.01,
                internal=False, open_alert=True,
                skymap_filename='bayestar.fits.gz', skymap_type='bayestar')
        send.assert_called_once()
        create_initial_circular.assert_called_once()
        create_label.assert_has_calls([call('ADVREQ', 'S1234')])

    if group == 'CBC' and not offline:
        query_data.assert_called_once()
        prepare_ini.assert_called_once()
        if far <= app.conf['pe_threshold']:
            start_pe.assert_called_once()
        else:
            start_pe.assert_not_called()


@patch('gwcelery.tasks.gracedb.get_labels', return_value={'DQV', 'ADVREQ'})
def test_handle_superevent_event_added(mock_get_labels):
    alert = {
        'alert_type': 'event_added',
        'uid': 'TS123456a',
        'data': {'superevent_id': 'TS123456a',
                 'preferred_event': 'G123456',
                 't_start': 1.,
                 't_0': 2.,
                 't_end': 3.},
        'object': {'superevent_id': 'TS123456a',
                   'preferred_event': 'G123456',
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
    elif filename == 'em_bright.json':
        return json.dumps({'HasNS': 0.0, 'HasRemnant': 0.0})
    elif filename == 'p_astro.json':
        return json.dumps(
            dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terrestrial=0.01))
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'tag_names': ['sky_loc', 'public'],
                      'filename': 'foobar.fits.gz'},
                     {'tag_names': ['em_bright'],
                      'filename': 'em_bright.json'},
                     {'tag_names': ['p_astro'],
                      'filename': 'p_astro.json'}])
@patch('gwcelery.tasks.gracedb.create_tag.run')
@patch('gwcelery.tasks.gracedb.create_voevent.run',
       return_value='S1234-Initial-1.xml')
@patch('gwcelery.tasks.gracedb.expose.run')
@patch('gwcelery.tasks.gracedb.download.run',
       superevent_initial_alert_download)
@patch('gwcelery.tasks.gcn.send.run')
@patch('gwcelery.tasks.circulars.create_initial_circular.run')
def test_handle_superevent_initial_alert(mock_create_initial_circular,
                                         mock_send, mock_expose,
                                         mock_create_voevent,
                                         mock_create_tag, mock_get_log):
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
        skymap_filename='foobar.fits.gz', skymap_type='foobar', vetted=True)
    mock_send.assert_called_once_with('contents of S1234-Initial-1.xml')
    mock_create_initial_circular.assert_called_once_with('S1234')
    mock_create_tag.assert_called_once_with(
        'S1234-Initial-1.xml', 'public', 'S1234')


def superevent_retraction_alert_download(filename, graceid):
    if filename == 'S1234-Retraction-2.xml':
        return 'contents of S1234-Retraction-2.xml'
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.create_tag.run')
@patch('gwcelery.tasks.gracedb.create_voevent.run',
       return_value='S1234-Retraction-2.xml')
@patch('gwcelery.tasks.gracedb.expose.run')
@patch('gwcelery.tasks.gracedb.download.run',
       superevent_retraction_alert_download)
@patch('gwcelery.tasks.gcn.send.run')
@patch('gwcelery.tasks.circulars.create_retraction_circular.run')
def test_handle_superevent_retraction_alert(mock_create_retraction_circular,
                                            mock_send, mock_expose,
                                            mock_create_voevent,
                                            mock_create_tag):
    """Test that the ``ADVNO`` label triggers a retraction alert."""
    alert = {
        'alert_type': 'label_added',
        'uid': 'S1234',
        'data': {'name': 'ADVNO'}
    }

    # Run function under test
    orchestrator.handle_superevent(alert)

    mock_expose.assert_called_once_with('S1234')
    mock_create_voevent.assert_called_once_with(
        'S1234', 'retraction', internal=False, open_alert=True, vetted=True)
    mock_send.assert_called_once_with('contents of S1234-Retraction-2.xml')
    mock_create_retraction_circular.assert_called_once_with('S1234')
    mock_create_tag.assert_called_once_with(
        'S1234-Retraction-2.xml', 'public', 'S1234')


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
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event(mock_gracedb, mock_localize, mock_get_event):
    """Test that an LVAlert message for a newly uploaded PSD file triggers
    BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_psd.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_called_once()


# FIXME calling em-bright point estimates for all pipelines until review
# is complete
@patch('gwcelery.tasks.em_bright.classifier_other.run')
def test_handle_cbc_event_new_event(mock_classifier):
    payload = {
        "uid": "G000003",
        "alert_type": "new",
        "description": "",
        "object": {
            "graceid": "G000003",
            "gpstime": 100.0,
            "pipeline": "gstlal",
            "group": "CBC",
            "search": "AllSky",
            "far": 1.e-31,
            "instruments": "H1,L1",
            "extra_attributes": {
                "CoincInspiral": {"snr": 20},
                "SingleInspiral": [{
                    "mass1": 3.0,
                    "mass2": 1.0,
                    "spin1z": 0.0,
                    "spin2z": 0.0,
                    "snr": 20,
                    "ifo": "H1",
                    "chisq": 1.571
                }]
            },
            "offline": False
        }
    }
    orchestrator.handle_cbc_event(payload)
    mock_classifier.assert_called_once()


@patch(
    'gwcelery.tasks.gracedb.get_event.run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal',
                  'far': 1e-7,
                  'extra_attributes':
                      {'CoincInspiral': {'snr': 10.},
                       'SingleInspiral': [{'mass1': 10., 'mass2': 5.}]}})
@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier_gstlal.run')
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


@patch('gwcelery.tasks.orchestrator._create_voevent')
@patch('gwcelery.tasks.circulars.create_initial_circular')
@patch('gwcelery.tasks.gcn.send')
@pytest.fixture(params=[{'INJ'}, {'DQV'}])
def test_inj_stops_prelim(monkeypatch, request, send, create_initial_circular,
                          create_voevent):
    event = {'group': 'burst', 'pipeline': 'pipeline', 'search': 'AllSky',
             'instruments': 'H1,L1,V1', 'graceid': 'G1234',
             'offline': False, 'far': 1.e-10, 'gpstime': 1234,
             'extra_attributes':
             {'CoincInspiral': {'ifos': 'H1,L1,V1'}}}
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_labels.run',
                        request.param)
    supereventid = 'S12345'
    orchestrator.preliminary_alert(event, supereventid)
    send.assert_not_called()
    create_initial_circular.assert_not_called()
    create_voevent.assert_not_called()
