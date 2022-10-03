from importlib import resources
import json
from unittest.mock import call, Mock, patch

import pytest

from .. import app
from ..tasks import inference
from ..tasks import orchestrator
from ..tasks import superevents
from ..util import read_json
from .test_tasks_skymaps import toy_3d_fits_filecontents  # noqa: F401
from . import data


@pytest.mark.parametrize(  # noqa: F811
    'alert_type,label,group,pipeline,offline,far,instruments',
    [['label_added', 'ADVREQ', 'CBC', 'gstlal', False, 1.e-9,
        ['H1']],
     ['label_added', 'ADVREQ', 'CBC', 'gstlal', False, 1.e-9,
         ['H1', 'L1']],
     ['label_added', 'ADVREQ', 'CBC', 'gstlal', False, 1.e-9,
         ['H1', 'L1', 'V1']],
     ['label_added', 'ADVREQ', 'Burst', 'CWB', False, 1.e-9,
         ['H1', 'L1', 'V1']],
     ['label_added', 'ADVREQ', 'Burst', 'oLIB', False, 1.e-9,
         ['H1', 'L1', 'V1']],
     ['label_added', 'GCN_PRELIM_SENT', 'CBC', 'gstlal', False, 1.e-9,
         ['H1', 'L1', 'V1']],
     ['new', '', 'CBC', 'gstlal', False, 1.e-9, ['H1', 'L1']]])
@pytest.mark.xfail(reason='https://github.com/celery/celery/issues/4405')
def test_handle_superevent(monkeypatch, toy_3d_fits_filecontents,  # noqa: F811
                           alert_type, label, group, pipeline,
                           offline, far, instruments):
    """Test a superevent is dispatched to the correct annotation task based on
    its preferred event's search group.
    """
    alert = {
        'alert_type': alert_type,
        'uid': 'S1234',
        'object': {
            'superevent_id': 'S1234',
            't_start': 1214714160,
            't_0': 1214714162,
            't_end': 1214714164,
            'preferred_event': 'G1234'
        },
        'data': {'name': label}
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
            'extra_attributes': {},
            'labels': ['ADVREQ', 'PASTRO_READY', 'EMBRIGHT_READY',
                       'SKYMAP_READY']
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
            with resources.path('psd.xml.gz') as p:
                return str(p)
        elif filename == 'S1234-1-Preliminary.xml':
            return b'fake VOEvent file contents'
        elif filename == 'p_astro.json':
            return json.dumps(
                dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terrestrial=0.01))
        elif filename == inference.ini_name:
            return 'test'
        else:
            raise ValueError

    create_initial_circular = Mock()
    expose = Mock()
    plot_volume = Mock()
    plot_allsky = Mock()
    gcn_send = Mock()
    alerts_send = Mock()
    query_data = Mock()
    prepare_ini = Mock()
    start_pe = Mock()
    create_voevent = Mock(return_value='S1234-1-Preliminary.xml')
    create_label = Mock()
    create_tag = Mock()
    # FIXME break up preliminary alert pipeline when removing xfail
    preliminary_alert_pipeline = Mock()
    select_preferred_event_task = Mock()
    omegascan = Mock()
    check_vectors = Mock()

    monkeypatch.setattr('gwcelery.tasks.gcn.send.run', gcn_send)
    monkeypatch.setattr('gwcelery.tasks.alerts.send.run',
                        alerts_send)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_allsky.run', plot_allsky)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_volume.run', plot_volume)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_tag._orig_run',
                        create_tag)
    monkeypatch.setattr('gwcelery.tasks.gracedb.download._orig_run', download)
    monkeypatch.setattr('gwcelery.tasks.gracedb.expose._orig_run', expose)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_event._orig_run',
                        get_event)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_voevent._orig_run',
                        create_voevent)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_superevent._orig_run',
                        get_superevent)
    monkeypatch.setattr('gwcelery.tasks.circulars.create_initial_circular.run',
                        create_initial_circular)
    monkeypatch.setattr('gwcelery.tasks.inference.query_data.run',
                        query_data)
    monkeypatch.setattr('gwcelery.tasks.inference.prepare_ini.run',
                        prepare_ini)
    monkeypatch.setattr('gwcelery.tasks.inference.start_pe.run',
                        start_pe)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_label._orig_run',
                        create_label)
    monkeypatch.setattr(
        'gwcelery.tasks.orchestrator.earlywarning_preliminary_alert.run',
        preliminary_alert_pipeline
    )
    monkeypatch.setattr(
        'gwcelery.tasks.superevents.select_preferred_event.run',
        select_preferred_event_task
    )
    monkeypatch.setattr('gwcelery.tasks.detchar.omegascan.run', omegascan)
    monkeypatch.setattr('gwcelery.tasks.detchar.check_vectors.run',
                        check_vectors)

    # Run function under test
    orchestrator.handle_superevent(alert)

    if label == 'GCN_PRELIM_SENT':
        create_label.assert_call_once_with('DQR_REQUEST', 'S1234')
        select_preferred_event_task.assert_called_once()
        preliminary_alert_pipeline.assert_called_once()
    elif alert_type == 'label_added':
        plot_allsky.assert_called_once()
        plot_volume.assert_called_once()

        _event_info = get_event('G1234')  # this gets the preferred event info
        assert superevents.should_publish(_event_info)
        expose.assert_called_once_with('S1234')
        create_tag.assert_called_once_with(
            'S1234-1-Preliminary.xml', 'public', 'S1234')
        if group == 'CBC':
            create_voevent.assert_called_once_with(
                'S1234', 'preliminary', BBH=0.02, BNS=0.94, NSBH=0.03,
                ProbHasNS=0.0, ProbHasRemnant=0.0, Terrestrial=0.01,
                internal=False, open_alert=True,
                skymap_filename='bayestar.fits.gz', skymap_type='bayestar')
        gcn_send.assert_called_once()
        alerts_send.assert_called_once()
        create_initial_circular.assert_called_once()

    if alert_type == 'new' and group == 'CBC':
        query_data.assert_called_once()
        prepare_ini.assert_called_once()
        if far <= app.conf['pe_threshold']:
            assert start_pe.call_count == 2
            # FIXME with proper arguments with lalinference and bilby
        else:
            start_pe.assert_not_called()

    if alert_type == 'new':
        omegascan.assert_called_once()
        check_vectors.assert_called_once()


@patch('gwcelery.tasks.gracedb.get_labels', return_value={'DQV', 'ADVREQ'})
@patch('gwcelery.tasks.detchar.check_vectors.run')
def test_handle_superevent_event_added(mock_check_vectors, mock_get_labels):
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
                   't_end': 3.,
                   'preferred_event_data': {
                       'graceid': 'G123456'
                   }}
    }
    orchestrator.handle_superevent(alert)
    mock_check_vectors.assert_called_once_with(
        {'graceid': 'G123456'}, 'TS123456a', 1., 3.)


def superevent_initial_alert_download(filename, graceid):
    if filename == 'S1234-Initial-1.xml':
        return 'contents of S1234-Initial-1.xml'
    elif filename == 'em_bright.json,0':
        return json.dumps({'HasNS': 0.0, 'HasRemnant': 0.0})
    elif filename == 'p_astro.json,0':
        return json.dumps(
            dict(BNS=0.94, NSBH=0.03, BBH=0.02, Terrestrial=0.01))
    elif filename == 'foobar.multiorder.fits,0':
        return 'contents of foobar.multiorder.fits,0'
    else:
        raise ValueError


@pytest.mark.parametrize(  # noqa: F811
    'labels',
    [[], ['EM_COINC', 'RAVEN_ALERT']])
@patch('gwcelery.tasks.gracedb.expose._orig_run', return_value=None)
@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'tag_names': ['sky_loc', 'public'],
                      'filename': 'foobar.multiorder.fits',
                      'file_version': 0},
                     {'tag_names': ['em_bright'],
                      'filename': 'em_bright.json',
                      'file_version': 0},
                     {'tag_names': ['p_astro'],
                      'filename': 'p_astro.json',
                      'file_version': 0}])
@patch('gwcelery.tasks.gracedb.create_tag._orig_run', return_value=None)
@patch('gwcelery.tasks.gracedb.create_voevent._orig_run',
       return_value='S1234-Initial-1.xml')
@patch('gwcelery.tasks.gracedb.download._orig_run',
       superevent_initial_alert_download)
@patch('gwcelery.tasks.gcn.send.run')
@patch('gwcelery.tasks.alerts.send.run')
@patch('gwcelery.tasks.circulars.create_emcoinc_circular.run')
@patch('gwcelery.tasks.circulars.create_initial_circular.run')
def test_handle_superevent_initial_alert(mock_create_initial_circular,
                                         mock_create_emcoinc_circular,
                                         mock_alerts_send,
                                         mock_gcn_send,
                                         mock_create_voevent,
                                         mock_create_tag, mock_get_log,
                                         mock_expose, labels):
    """Test that the ``ADVOK`` label triggers an initial alert."""
    alert = {
        'alert_type': 'label_added',
        'uid': 'S1234',
        'data': {'name': 'ADVOK'},
        'object': {
            'labels': labels,
            'superevent_id': 'S1234'
        }
    }

    # Run function under test
    orchestrator.handle_superevent(alert)

    mock_create_voevent.assert_called_once_with(
        'S1234', 'initial', BBH=0.02, BNS=0.94, NSBH=0.03, ProbHasNS=0.0,
        ProbHasRemnant=0.0, Terrestrial=0.01, internal=False, open_alert=True,
        skymap_filename='foobar.multiorder.fits,0', skymap_type='foobar',
        raven_coinc='RAVEN_ALERT' in labels)
    mock_alerts_send.assert_called_once_with((
        superevent_initial_alert_download('foobar.multiorder.fits,0', 'S1234'),
        superevent_initial_alert_download('em_bright.json,0', 'S1234'),
        superevent_initial_alert_download('p_astro.json,0', 'S1234'),
        None, None, None, None), alert['object'], 'initial',
        raven_coinc='RAVEN_ALERT' in labels)
    mock_gcn_send.assert_called_once_with('contents of S1234-Initial-1.xml')
    if 'RAVEN_ALERT' in labels:
        mock_create_emcoinc_circular.assert_called_once_with('S1234')
    else:
        mock_create_initial_circular.assert_called_once_with('S1234')
    mock_create_tag.assert_has_calls(
        [call('foobar.multiorder.fits,0', 'public', 'S1234'),
         call('em_bright.json,0', 'public', 'S1234'),
         call('p_astro.json,0', 'public', 'S1234'),
         call('S1234-Initial-1.xml', 'public', 'S1234')],
        any_order=True)
    mock_expose.assert_called_once_with('S1234')


def superevent_retraction_alert_download(filename, graceid):
    if filename == 'S1234-Retraction-2.xml':
        return 'contents of S1234-Retraction-2.xml'
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.expose._orig_run', return_value=None)
@patch('gwcelery.tasks.gracedb.create_tag._orig_run')
@patch('gwcelery.tasks.gracedb.create_voevent._orig_run',
       return_value='S1234-Retraction-2.xml')
@patch('gwcelery.tasks.gracedb.download._orig_run',
       superevent_retraction_alert_download)
@patch('gwcelery.tasks.gcn.send.run')
@patch('gwcelery.tasks.alerts.send.run')
@patch('gwcelery.tasks.circulars.create_retraction_circular.run')
def test_handle_superevent_retraction_alert(mock_create_retraction_circular,
                                            mock_alerts_send,
                                            mock_gcn_send,
                                            mock_create_voevent,
                                            mock_create_tag, mock_expose):
    """Test that the ``ADVNO`` label triggers a retraction alert."""
    alert = {
        'alert_type': 'label_added',
        'uid': 'S1234',
        'data': {'name': 'ADVNO'},
        'object': {
            'labels': [],
            'superevent_id': 'S1234'
        }
    }

    # Run function under test
    orchestrator.handle_superevent(alert)

    mock_create_voevent.assert_called_once_with(
        'S1234', 'retraction', internal=False, open_alert=True)
    mock_gcn_send.assert_called_once_with('contents of S1234-Retraction-2.xml')
    mock_alerts_send.assert_called_once_with(None, alert['object'],
                                             'retraction')
    mock_create_retraction_circular.assert_called_once_with('S1234')
    mock_create_tag.assert_called_once_with(
        'S1234-Retraction-2.xml', 'public', 'S1234')
    mock_expose.assert_called_once_with('S1234')


def mock_download(filename, graceid, *args, **kwargs):
    assert graceid == 'M394156'
    filenames = {'coinc.xml': 'coinc.xml',
                 'ranking_data.xml.gz': 'ranking_data_G322589.xml.gz'}
    return resources.read_binary(data, filenames[filename])


@pytest.mark.parametrize(
    'alert_type,filename',
    [['new', ''], ['log', 'psd.xml.gz'],
     ['log', 'test.posterior_samples.hdf5']])
def test_handle_posterior_samples(monkeypatch, alert_type, filename):
    alert = {
        'alert_type': alert_type,
        'uid': 'S1234',
        'data': {'comment': 'samples', 'filename': filename}
    }

    download = Mock()
    em_bright_pe = Mock()
    skymap_from_samples = Mock()
    fits_header = Mock()
    plot_allsky = Mock()
    annotate_fits_volume = Mock()
    upload = Mock()
    flatten = Mock()

    monkeypatch.setattr('gwcelery.tasks.em_bright.em_bright_posterior_'
                        'samples.run', em_bright_pe)
    monkeypatch.setattr('gwcelery.tasks.gracedb.download._orig_run', download)
    monkeypatch.setattr('gwcelery.tasks.skymaps.skymap_from_samples.run',
                        skymap_from_samples)
    monkeypatch.setattr('gwcelery.tasks.skymaps.fits_header.run', fits_header)
    monkeypatch.setattr('gwcelery.tasks.skymaps.plot_allsky.run', plot_allsky)
    monkeypatch.setattr('gwcelery.tasks.skymaps.annotate_fits_volume.run',
                        annotate_fits_volume)
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload._orig_run', upload)
    monkeypatch.setattr('gwcelery.tasks.skymaps.flatten.run', flatten)

    # Run function under test
    orchestrator.handle_posterior_samples(alert)

    if alert['alert_type'] != 'log' or \
            not alert['data']['filename'].endswith('.posterior_samples.hdf5'):
        skymap_from_samples.assert_not_called()
        fits_header.assert_not_called()
        plot_allsky.assert_not_called()
        annotate_fits_volume.assert_not_called()
        flatten.assert_not_called()
    else:
        em_bright_pe.assert_called_once()
        skymap_from_samples.assert_called_once()
        fits_header.assert_called_once()
        plot_allsky.assert_called_once()
        annotate_fits_volume.assert_called_once()
        flatten.assert_called_once()


@patch('gwcelery.tasks.gracedb.download._orig_run', mock_download)
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.em_bright.classifier_gstlal.run')
def test_handle_cbc_event_new_event(mock_classifier, mock_localize):
    alert = read_json(data, 'lvalert_event_creation.json')
    orchestrator.handle_cbc_event(alert)
    mock_classifier.assert_called_once()
    mock_localize.assert_called_once()


@patch(
    'gwcelery.tasks.gracedb.get_event._orig_run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal',
                  'far': 1e-7, 'labels': [],
                  'extra_attributes':
                      {'CoincInspiral': {'snr': 10.},
                       'SingleInspiral': [{'mass1': 10., 'mass2': 5.}]}})
@patch('gwcelery.tasks.gracedb.download._orig_run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier_gstlal.run')
@patch('gwcelery.tasks.bayestar.localize.run')
def test_handle_cbc_event_ignored(mock_localize,
                                  mock_classifier,
                                  mock_get_event):
    """Test that unrelated LVAlert messages do not trigger BAYESTAR."""
    alert = read_json(data, 'igwn_alert_detchar.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.live_worker
@patch('gwcelery.tasks.gcn.send')
@patch('gwcelery.tasks.alerts.send')
def test_alerts_skip_inj(mock_gcn_send, mock_alerts_send):
    orchestrator.earlywarning_preliminary_alert.delay(
        ('bayestar.fits.gz', 'em_bright.json', 'p_astro.json'),
        {'superevent_id': 'S1234', 'labels': ['INJ']},
        'preliminary'
    ).get()
    mock_gcn_send.assert_not_called()
    mock_alerts_send.assert_not_called()


@pytest.fixture
def only_mdc_alerts(monkeypatch):
    monkeypatch.setitem(app.conf, 'only_alert_for_mdc', True)


@pytest.mark.live_worker
@patch('gwcelery.tasks.skymaps.flatten')
@patch('gwcelery.tasks.gracedb.download')
@patch('gwcelery.tasks.gracedb.upload')
@patch('gwcelery.tasks.alerts.send')
def test_only_mdc_alerts_switch(mock_alert, mock_upload, mock_download,
                                mock_flatten, only_mdc_alerts):
    """Test to ensure that if the `only_alert_for_mdc` configuration variable
    is True, only events with search type "MDC" can result in alerts.
    """
    for search in ['AllSky', 'GRB', 'BBH']:
        event_dictionary = {'graceid': 'G2',
                            'gpstime': 1239917954.40918,
                            'far': 5.57979637960671e-06,
                            'group': 'CBC',
                            'search': search,
                            'instruments': 'H1,L1',
                            'pipeline': 'spiir',
                            'offline': False,
                            'labels': []}
        superevent_id = 'S1234'
        orchestrator.earlywarning_preliminary_alert.delay(
            event_dictionary,
            superevent_id,
            'preliminary'
        ).get()
        mock_alert.assert_not_called()
