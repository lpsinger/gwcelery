from unittest.mock import call, patch

import pytest

from .test_tasks_skymaps import toy_fits_filecontents  # noqa: F401
from ..tasks import gracedb, raven


@pytest.mark.parametrize(
    'group,gracedb_id,pipelines,tl,th',
    [['CBC', 'S1', ['Fermi', 'Swift'], -1, 5],
     ['Burst', 'S2', ['Fermi', 'Swift'], -60, 600],
     ['Burst', 'S3', ['SNEWS'], -10, 10],
     ['CBC', 'E1', ['Fermi'], -5, 1]])
@patch('gwcelery.tasks.gracedb.create_label.run')
@patch('gwcelery.tasks.raven.raven_pipeline.run')
@patch('gwcelery.tasks.raven.search.run', return_value=[{'superevent_id': 'S5',
                                                         'graceid': 'E2'}])
@patch('gwcelery.tasks.raven.calculate_coincidence_far.run')
def test_coincidence_search(mock_calculate_coincidence_far,
                            mock_search, mock_raven_pipeline,
                            mock_create_label,
                            group, gracedb_id, pipelines, tl, th):
    """Test that correct time windows are used for each RAVEN search."""
    alert_object = {'superevent_id': gracedb_id}

    raven.coincidence_search(gracedb_id, alert_object, group,
                             pipelines)

    mock_search.assert_called_once_with(
        gracedb_id, alert_object, tl, th, group, pipelines)
    mock_raven_pipeline.assert_called_once_with(
        [{'superevent_id': 'S5', 'graceid': 'E2'}],
        gracedb_id, alert_object, group)


@pytest.mark.parametrize(
    'event_type,event_id', [['SE', 'S1234'], ['ExtTrig', 'E1234']])
@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
@patch('ligo.raven.search.search')
def test_raven_search(mock_raven_search, mock_se_cls, mock_exttrig_cls,
                      event_type, event_id):
    """Test that correct input parameters are used for raven."""
    alert_object = {}
    if event_type == 'SE':
        alert_object['superevent_id'] = event_id

    # call raven search
    raven.search(event_id, alert_object)
    if event_id == 'S1234':
        mock_raven_search.assert_called_once_with(
            mock_se_cls(event_id, gracedb=gracedb.client), -5, 5,
            gracedb=gracedb.client, group=None, pipelines=[])
    elif event_id == 'E1234':
        mock_raven_search.assert_called_once_with(
            mock_exttrig_cls(event_id, gracedb=gracedb.client), -5, 5,
            gracedb=gracedb.client, group=None, pipelines=[])
    else:
        raise ValueError


@pytest.mark.parametrize('group', ['CBC', 'Burst'])
@patch('gwcelery.tasks.gracedb.get_search.run', return_value='GRB')
@patch('gwcelery.tasks.raven.calc_signif.run')
def test_calculate_coincidence_far(
        mock_calc_signif, mock_get_search, group):
    raven.calculate_coincidence_far('S1234', 'E4321',
                                    'G222', group)
    mock_get_search.assert_called_once_with('E4321')
    if group == 'CBC':
        tl, th = -5, 1
    else:
        tl, th = -600, 60
    mock_calc_signif.assert_called_once_with('GRB', 'S1234',
                                             'E4321', tl, th,
                                             incl_sky=False)


@pytest.mark.parametrize('group', ['CBC', 'Burst'])  # noqa: F811
@patch('gwcelery.tasks.ligo_fermi_skymaps.get_preferred_skymap',
       return_value='bayestar.fits.gz')
@patch('gwcelery.tasks.gracedb.get_search.run', return_value='GRB')
@patch('gwcelery.tasks.raven.calc_signif.run')
def test_calculate_spacetime_coincidence_far(
        mock_calc_signif, mock_get_search, mock_get_preferred_skymap,
        group):
    raven.calculate_coincidence_far(
        'S1234', 'E4321', 'G222', group)
    mock_get_search.assert_called_once_with('E4321')
    if group == 'CBC':
        tl, th = -5, 1
    else:
        tl, th = -600, 60
    mock_calc_signif.assert_called_once_with('GRB', 'S1234',
                                             'E4321', tl, th,
                                             incl_sky=True,
                                             se_fitsfile='bayestar.fits.gz')


@patch('ligo.raven.search.calc_signif_gracedb')
def test_calc_signif(
        mock_raven_calc_signif):
    tl, th = -1, 5
    raven.calc_signif('GRB', 'S1234', 'E1234', tl, th,
                      incl_sky=False)

    mock_raven_calc_signif.assert_called_once_with(
        'S1234', 'E1234', tl, th, grb_search='GRB',
        se_fitsfile=None, incl_sky=False,
        gracedb=gracedb.client)


@patch('ligo.raven.search.calc_signif_gracedb')
def test_calc_signif_skymaps(mock_raven_calc_signif):
    tl, th = -1, 5
    raven.calc_signif('GRB', 'S1234', 'E1234', tl, th,
                      incl_sky=True, se_fitsfile='bayestar.fits.gz')

    mock_raven_calc_signif.assert_called_once_with(
        'S1234', 'E1234', tl, th, grb_search='GRB',
        se_fitsfile='bayestar.fits.gz',
        incl_sky=True, gracedb=gracedb.client)


@pytest.mark.parametrize(
    'raven_search_results,graceid,group',
    [[[{'graceid': 'E1'}], 'S1', 'CBC'],
     [[{'superevent_id': 'S10', 'far': 1, 'preferred_event': 'G1'}],
        'E2', 'Burst'],
     [[{'graceid': 'E3'}, {'graceid': 'E4'}], 'S2', 'Burst'],
     [[{'superevent_id': 'S11', 'far': 1, 'preferred_event': 'G2'},
       {'superevent_id': 'S12', 'far': .001, 'preferred_event': 'G3'}],
        'E5', 'CBC'],
     [[], 'S15', 'Group']])
@patch('gwcelery.tasks.raven.calculate_coincidence_far.run')
@patch('gwcelery.tasks.gracedb.create_label.run')
def test_raven_pipeline(mock_create_label,
                        mock_calculate_coincidence_far,
                        raven_search_results, graceid, group):

    alert_object = {'preferred_event': 'G1'}
    raven.raven_pipeline(raven_search_results, graceid, alert_object, group)

    coinc_calls = []
    label_calls = []
    if not raven_search_results:
        mock_calculate_coincidence_far.assert_not_called()
        mock_create_label.assert_not_called()
        return
    elif graceid.startswith('E'):
        result = raven.preferred_superevent(raven_search_results)[0]
        label_calls.append(call('EM_COINC', result['superevent_id']))
        coinc_calls.append(call(result['superevent_id'], graceid,
                                result['preferred_event'], group))
        label_calls.append(call('EM_COINC', graceid))
    else:
        for result in raven_search_results:
            label_calls.append(call('EM_COINC', result['graceid']))
            coinc_calls.append(call(graceid, result['graceid'],
                                    alert_object['preferred_event'], group))
            label_calls.append(call('EM_COINC', graceid))

    mock_calculate_coincidence_far.assert_has_calls(coinc_calls,
                                                    any_order=True)
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
