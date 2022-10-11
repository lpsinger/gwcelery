from unittest.mock import call, patch

import pytest

from .test_tasks_skymaps import toy_fits_filecontents  # noqa: F401
from ..tasks import gracedb
from ..tasks import raven


@pytest.mark.live_worker
@pytest.mark.parametrize(
    'group,gracedb_id,pipelines,ext_search,se_search,tl,th',
    [['CBC', 'S1', ['Fermi', 'Swift'], [], ['GRB'], -1, 5],
     ['Burst', 'S2', ['Fermi', 'Swift'], [], ['GRB'], -60, 600],
     ['Burst', 'S3', ['SNEWS'], ['Supernova'], [], -10, 10],
     ['Burst', 'T4', ['SNEWS'], 'Supernova', [], -10, 10],
     ['CBC', 'MS4', ['Fermi'], ['MDC'], [], -1, 5],
     ['CBC', 'E1', ['Fermi'], [], ['GRB'], -5, 1],
     ['CBC', 'M1', ['Fermi'], [], ['MDC'], -5, 1]])
@patch('gwcelery.tasks.gracedb.create_label')
@patch('gwcelery.tasks.raven.raven_pipeline.s')
@patch('gwcelery.tasks.raven.search.si', return_value=[{'superevent_id': 'S5',
                                                        'graceid': 'E2'}])
@patch('gwcelery.tasks.raven.calculate_coincidence_far')
def test_coincidence_search(mock_calculate_coincidence_far,
                            mock_search, mock_raven_pipeline,
                            mock_create_label,
                            group, gracedb_id, pipelines,
                            ext_search, se_search, tl, th):
    """Test that correct time windows are used for each RAVEN search."""
    alert_object = {'superevent_id': gracedb_id}
    if 'E' in gracedb_id:
        alert_object['group'] = 'External'
    raven.coincidence_search(gracedb_id, alert_object, group,
                             pipelines, ext_search, se_search)

    mock_search.assert_called_once_with(
        gracedb_id, alert_object, tl, th, group, pipelines,
        ext_search, se_search)
    mock_raven_pipeline.assert_called_once_with(
        gracedb_id, alert_object, tl, th, group)


@pytest.mark.parametrize(
    'event_type,event_id', [['SE', 'S1234'], ['ExtTrig', 'E1234']])
@patch('ligo.raven.search.search')
def test_raven_search(mock_raven_search, event_type, event_id):
    """Test that correct input parameters are used for raven."""
    alert_object = {}
    if event_type == 'SE':
        alert_object['superevent_id'] = event_id

    # call raven search
    raven.search(event_id, alert_object)
    mock_raven_search.assert_called_once_with(
        event_id, -5, 5, event_dict=alert_object,
        gracedb=gracedb.client, group=None, pipelines=[], searches=[],
        se_searches=[])


@pytest.mark.parametrize('group', ['CBC', 'Burst'])
@patch('ligo.raven.search.calc_signif_gracedb')
def test_calculate_coincidence_far(
        mock_calc_signif, group):
    se = {'superevent_id': 'S1234'}
    ext = {'graceid': 'E4321',
           'pipeline': 'Fermi',
           'search': 'GRB',
           'labels': [],
           'far': None}
    if group == 'CBC':
        tl, th = -5, 1
    else:
        tl, th = -600, 60
    raven.calculate_coincidence_far(se, ext, tl, th)
    mock_calc_signif.assert_called_once_with(
        'S1234', 'E4321', tl, th,
        se_dict=se, ext_dict=ext,
        incl_sky=False, grb_search='GRB',
        gracedb=gracedb.client, far_grb=None)


@patch('ligo.raven.search.calc_signif_gracedb')
def test_calculate_coincidence_far_subgrb(mock_calc_signif):
    se = {'superevent_id': 'S1234'}
    ext = {'graceid': 'E4321',
           'pipeline': 'Fermi',
           'search': 'GRB',
           'labels': [],
           'far': 1e5}
    tl, th = -1, 10
    raven.calculate_coincidence_far(se, ext, tl, th)
    mock_calc_signif.assert_called_once_with(
        'S1234', 'E4321', tl, th,
        se_dict=se, ext_dict=ext,
        incl_sky=False, grb_search='GRB',
        gracedb=gracedb.client, far_grb=1e5)


@pytest.mark.parametrize('group', ['CBC', 'Burst'])  # noqa: F811
@patch('gwcelery.tasks.external_skymaps.get_skymap_filename',
       return_value='fermi_skymap.fits.gz')
@patch('ligo.raven.search.calc_signif_gracedb')
def test_calculate_spacetime_coincidence_far_fermi(
        mock_calc_signif, mock_get_skymap_filename, group):
    se = {'superevent_id': 'S1234'}
    ext = {'graceid': 'E4321',
           'pipeline': 'Fermi',
           'search': 'GRB',
           'labels': ['EXT_SKYMAP_READY', 'SKYMAP_READY'],
           'far': None}
    if group == 'CBC':
        tl, th = -5, 1
    else:
        tl, th = -600, 60
    raven.calculate_coincidence_far(se, ext, tl, th)
    mock_calc_signif.assert_called_once_with(
        'S1234', 'E4321', tl, th,
        incl_sky=True, grb_search='GRB',
        se_dict=se, ext_dict=ext,
        se_fitsfile='fermi_skymap.fits.gz',
        ext_fitsfile='fermi_skymap.fits.gz',
        se_moc=True, ext_moc=False,
        use_radec=False,
        gracedb=gracedb.client, far_grb=None)


@pytest.mark.parametrize('group', ['CBC', 'Burst'])  # noqa: F811
@patch('gwcelery.tasks.external_skymaps.get_skymap_filename',
       return_value='swift_skymap.fits.gz')
@patch('ligo.raven.search.calc_signif_gracedb')
def test_calculate_spacetime_coincidence_far_swift(
        mock_calc_signif, mock_get_skymap_filename, group):
    se = {'superevent_id': 'S1234'}
    ext = {'graceid': 'E4321',
           'pipeline': 'Swift',
           'search': 'GRB',
           'labels': ['EXT_SKYMAP_READY', 'SKYMAP_READY'],
           'far': None}
    if group == 'CBC':
        tl, th = -5, 1
    else:
        tl, th = -600, 60
    raven.calculate_coincidence_far(se, ext, tl, th)
    mock_calc_signif.assert_called_once_with(
        'S1234', 'E4321', tl, th,
        incl_sky=True, grb_search='GRB',
        se_dict=se, ext_dict=ext,
        se_fitsfile='swift_skymap.fits.gz',
        ext_fitsfile='swift_skymap.fits.gz',
        se_moc=True, ext_moc=False,
        use_radec=True,
        gracedb=gracedb.client, far_grb=None)


def mock_get_labels(superevent_id):
    if superevent_id == 'S14':
        return {'ADVREQ'}
    else:
        return {}


def mock_coinc_far(*args):
    return {'temporal_coinc_far': 1e-7,
            'spatiotemporal_coinc_far': None}


@pytest.mark.parametrize(
    'raven_search_results,graceid,tl,th,group',
    [[[{'graceid': 'E1', 'pipeline': 'GRB'}], 'S1', -5, 1, 'CBC'],
     [[{'superevent_id': 'S10', 'far': 1, 'preferred_event': 'G1'}],
        'E2', -1, 5, 'CBC'],
     [[{'graceid': 'E3', 'pipeline': 'GRB'},
       {'graceid': 'E4', 'pipeline': 'GRB'}], 'S2', -600, 60, 'Burst'],
     [[{'superevent_id': 'S11', 'far': 1, 'preferred_event': 'G2'},
       {'superevent_id': 'S12', 'far': .001, 'preferred_event': 'G3'}],
        'E5', -1, 5, 'CBC'],
     [[], 'S13', -1, 5, 'CBC'],
     [[{'graceid': 'E4', 'pipeline': 'GRB'}], 'S14', -1, 5, 'CBC'],
     [[{'superevent_id': 'S12', 'far': .001, 'preferred_event': 'G3'}],
        'T4', -10, 10, 'Burst'],
     [[{'superevent_id': 'MS13', 'far': 1, 'preferred_event': 'M3'}],
        'M15', -1, 5, 'CBC']])
@patch('gwcelery.tasks.raven.trigger_raven_alert.run')
@patch('gwcelery.tasks.gracedb.get_labels', mock_get_labels)
@patch('gwcelery.tasks.raven.calculate_coincidence_far.run',
       return_value=mock_coinc_far())
@patch('gwcelery.tasks.gracedb.update_superevent')
@patch('gwcelery.tasks.gracedb.create_label.run')
def test_raven_pipeline(mock_create_label,
                        mock_update_superevent,
                        mock_calculate_coincidence_far,
                        mock_trigger_raven_alert,
                        raven_search_results, graceid, tl, th, group):
    """This function tests that the RAVEN pipeline runs correctly for scenarios
    where RAVEN finds nothing, a coincidence is found but does not pass
    threshold, when a coincidence is found but does pass threshold, and when
    multiple events are found.
    """
    alert_object = {'preferred_event': 'G1', 'pipeline': 'Fermi',
                    'search': 'Supernova' if graceid == 'T4' else 'GRB',
                    'labels': []}
    time_coinc_far = mock_coinc_far()['temporal_coinc_far']
    space_coinc_far = mock_coinc_far()['spatiotemporal_coinc_far']
    for result in raven_search_results:
        result['labels'] = []
    if 'S' not in graceid:
        alert_object['group'] = 'External'
        if 'T' in graceid:
            alert_object['group'] = 'Test'
        alert_object['graceid'] = graceid
        for result in raven_search_results:
            result['time_coinc_far'] = 1e-5
            result['space_coinc_far'] = None
    else:
        alert_object['superevent_id'] = graceid
        alert_object['time_coinc_far'] = 1e-5
        alert_object['space_coinc_far'] = None
    raven.raven_pipeline(raven_search_results, graceid, alert_object, tl, th,
                         group)

    coinc_calls = []
    label_calls = []
    update_calls = []
    if not raven_search_results:
        mock_calculate_coincidence_far.assert_not_called()
        mock_create_label.assert_not_called()
        return
    if 'S' in graceid:
        for result in raven_search_results:
            label_calls.append(call('EM_COINC', result['graceid']))
            coinc_calls.append(call(alert_object, result, tl, th))
            label_calls.append(call('EM_COINC', graceid))
            update_calls.append(
                call(graceid, em_type=result['graceid'],
                     time_coinc_far=time_coinc_far,
                     space_coinc_far=space_coinc_far))
    else:
        result = raven.preferred_superevent(raven_search_results)[0]
        label_calls.append(call('EM_COINC', result['superevent_id']))
        coinc_calls.append(call(result, alert_object, tl, th))
        label_calls.append(call('EM_COINC', graceid))
        update_calls.append(
            call(raven_search_results[-1]['superevent_id'],
                 em_type=graceid,
                 time_coinc_far=time_coinc_far,
                 space_coinc_far=space_coinc_far))

    alert_calls = []
    if 'S' in graceid:
        for result in raven_search_results:
            alert_calls.append(call(mock_coinc_far(),
                                    alert_object, graceid, result, group))
    else:
        alert_calls.append(call(
            mock_coinc_far(),
            result, graceid, alert_object, group))
    mock_trigger_raven_alert.assert_has_calls(alert_calls, any_order=True)

    mock_calculate_coincidence_far.assert_has_calls(coinc_calls,
                                                    any_order=True)
    mock_update_superevent.assert_has_calls(update_calls, any_order=True)
    mock_create_label.assert_has_calls(label_calls, any_order=True)


@pytest.mark.parametrize(
    'raven_search_results, testnum',
    [[[{'superevent_id': 'S10', 'far': 1, 'preferred_event': 'G1'}], 1],
     [[{'superevent_id': 'S11', 'far': 1, 'preferred_event': 'G2'},
       {'superevent_id': 'S12', 'far': .001, 'preferred_event': 'G3'}], 2],
     [[{'superevent_id': 'S13', 'far': 1, 'preferred_event': 'G4'},
       {'superevent_id': 'S14', 'far': .0001, 'preferred_event': 'G5'},
       {'superevent_id': 'S15', 'far': .001, 'preferred_event': 'G6'}], 3]])
def test_preferred_superevent(raven_search_results, testnum):

    preferred_superevent = raven.preferred_superevent(raven_search_results)
    if testnum == 1:
        assert preferred_superevent == [{'superevent_id': 'S10', 'far': 1,
                                         'preferred_event': 'G1'}]
    if testnum == 2:
        assert preferred_superevent == [{'superevent_id': 'S12', 'far': .001,
                                         'preferred_event': 'G3'}]
    if testnum == 3:
        assert preferred_superevent == [{'superevent_id': 'S14', 'far': .0001,
                                         'preferred_event': 'G5'}]


@pytest.mark.parametrize(
    'new_time_far,new_space_far,old_time_far,old_space_far,pipeline,result',
    [[1e-4, None, None, None, 'Fermi', True],
     [1e-4, 1e-3, None, None, 'Swift', True],
     [1e-4, None, 1e-5, None, 'AGILE', False],
     [1e-4, 1e-3, 1e-4, None, 'Fermi', True],
     [1e-4, 1e-3, 1e-5, 1e-6, 'Fermi', False],
     [1e-8, None, 1e-5, 1e-6, 'Swift', False],
     [1e-4, 1e-8, 1e-4, 1e-6, 'AGILE', True],
     [None, None, None, None, 'SNEWS', True]])
@patch('gwcelery.tasks.gracedb.update_superevent')
def test_update_superevent(mock_update_superevent,
                           new_time_far, new_space_far,
                           old_time_far, old_space_far,
                           pipeline, result):

    superevent = {'time_coinc_far': old_time_far,
                  'space_coinc_far': old_space_far,
                  'superevent_id': 'S100'}
    ext_event = {'graceid': 'E100',
                 'pipeline': pipeline}
    coinc_far_dict = {'temporal_coinc_far': new_time_far,
                      'spatiotemporal_coinc_far': new_space_far}
    raven.update_coinc_far(coinc_far_dict, superevent, ext_event)
    if result:
        mock_update_superevent.assert_called_with(
            'S100', em_type='E100',
            time_coinc_far=new_time_far,
            space_coinc_far=new_space_far)
    else:
        mock_update_superevent.assert_not_called()


def _mock_get_event(graceid):
    if graceid == "S1234":
        return {"superevent_id": "S1234",
                "preferred_event": "G000001",
                "preferred_event_data": {"group": "Burst"},
                "far": 1e-5}
    elif graceid == "S2345":
        return {"superevent_id": "S2345",
                "preferred_event": "G000002",
                "preferred_event_data": {"group": "Burst"},
                "far": 1e-10}
    elif graceid == "S2468":
        return {"superevent_id": "S2468",
                "preferred_event": "G000002",
                "preferred_event_data": {"group": "CBC"},
                "far": 1e-4}
    elif graceid == "S5678":
        return {"superevent_id": "S5678",
                "preferred_event": "G000003",
                "preferred_event_data": {"group": "CBC"},
                "far": 1e-5}
    elif graceid == "S8642":
        return {"superevent_id": "S8642",
                "preferred_event": "G000003",
                "preferred_event_data": {"group": "Burst"},
                "far": 1e-3}
    elif graceid == "S9876":
        return {"superevent_id": "S9876",
                "preferred_event": "G000003",
                "preferred_event_data": {"group": "Burst"},
                "far": 1e-6}
    elif graceid == "TS1111":
        return {"superevent_id": "TS1111",
                "preferred_event": "G000003",
                "preferred_event_data": {"group": "Test"},
                "far": 1e-6}
    elif graceid == "MS1111":
        return {"superevent_id": "MS1111",
                "preferred_event": "M000004",
                "preferred_event_data": {"group": "CBC"},
                "far": 1e-9}
    elif graceid == 'E1':
        return {"graceid": "E1",
                "pipeline": 'Swift',
                "search": 'GRB',
                "labels": [],
                "group": 'External'}
    elif graceid == 'E2':
        return {"graceid": "E2",
                "pipeline": 'Fermi',
                "search": 'SubGRB',
                "labels": [],
                "group": 'External'}
    elif graceid == 'E3':
        return {"graceid": "E3",
                "pipeline": 'SNEWS',
                "search": 'Supernova',
                "labels": [],
                "group": 'External'}
    elif graceid == 'T4':
        return {"graceid": "T4",
                "pipeline": 'SNEWS',
                "search": 'Supernova',
                "labels": [],
                "group": 'Test'}
    elif graceid == 'E5':
        return {"graceid": "E5",
                "pipeline": 'Fermi',
                "search": 'GRB',
                "labels": ['NOT_GRB'],
                "group": 'External'}
    elif graceid == 'M5':
        return {"graceid": "M5",
                "pipeline": 'Fermi',
                "search": 'MDC',
                "labels": [],
                "group": 'External'}
    else:
        raise AssertionError


def _mock_get_labels(graceid):
    return _mock_get_event(graceid)['labels']


def _mock_get_coinc_far(graceid):
    if graceid == "S1234":
        return {"temporal_coinc_far": 1e-12,
                "spatiotemporal_coinc_far": 1e-05}
    elif graceid == "S2468":
        return {"temporal_coinc_far": 1e-09,
                "spatiotemporal_coinc_far": None}
    elif graceid == "S5678":
        return {"temporal_coinc_far": 1e-15,
                "spatiotemporal_coinc_far": None}
    elif graceid == "S8642":
        return {"temporal_coinc_far": 1e-03,
                "spatiotemporal_coinc_far": None}
    elif graceid == "S9876":
        return {"temporal_coinc_far": 1e-07,
                "spatiotemporal_coinc_far": 1e-13}
    elif graceid == "MS1111":
        return {"temporal_coinc_far": 1e-09,
                "spatiotemporal_coinc_far": 1e-10}
    else:
        return {}


@pytest.mark.parametrize(
    'graceid,result_id,group,expected_result',
    [['S1234', 'E1', 'Burst', False],
     ['S2468', 'E1', 'CBC', False],
     ['S2468', 'E5', 'CBC', False],
     ['S2468', 'E2', 'CBC', False],
     ['S2345', 'E3', 'Burst', True],
     ['MS1111', 'M5', 'CBC', True],
     ['E1', 'S9876', 'CBC', True],
     ['E1', 'S2468', 'CBC', False],
     ['E2', 'S5678', 'CBC', False],
     ['E3', 'S8642', 'Burst', False],
     ['E3', 'S9876', 'Burst', True],
     ['T4', 'TS1111', 'CBC', False],
     ['E5', 'S5678', 'CBC', False]])
@patch('gwcelery.tasks.gracedb.get_labels', side_effect=_mock_get_labels)
@patch('gwcelery.tasks.gracedb.update_superevent')
@patch('gwcelery.tasks.gracedb.create_label.run')
def test_trigger_raven_alert(mock_create_label, mock_update_superevent,
                             mock_get_labels,
                             graceid, result_id, group, expected_result):
    if 'S' in graceid:
        superevent_id = graceid
        ext_id = result_id
    else:
        superevent_id = result_id
        ext_id = graceid
    superevent = _mock_get_event(superevent_id)
    coinc_far_json = _mock_get_coinc_far(superevent_id)
    ext_event = _mock_get_event(ext_id)
    preferred_id = superevent['preferred_event']
    raven.trigger_raven_alert(coinc_far_json, superevent,
                              graceid, ext_event, group)

    if expected_result:
        label_calls = [call('RAVEN_ALERT', superevent_id),
                       call('RAVEN_ALERT', ext_id),
                       call('RAVEN_ALERT', preferred_id)]
        mock_create_label.assert_has_calls(label_calls)
    else:
        mock_create_label.assert_not_called()
