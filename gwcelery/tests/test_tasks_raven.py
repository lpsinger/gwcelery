from unittest.mock import call, patch

import pytest

from .test_tasks_skymaps import toy_fits_filecontents  # noqa: F401
from ..tasks import gracedb, raven


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


@pytest.mark.parametrize(
    'graceid,raven_search_results',
    [['S1234', [{'graceid': 'E1'}, {'graceid': 'E2'}, {'graceid': 'E3'}]],
     ['E1234', [{'superevent_id': 'S1'}]]])
def test_add_exttrig_to_superevent(monkeypatch, graceid, raven_search_results):
    """Test that external triggers are correctly used to update superevents."""

    # run function under test
    raven.add_exttrig_to_superevent(raven_search_results, graceid)
    if graceid.startswith('E'):
        for superevent in raven_search_results:
            superevent_id = superevent['superevent_id']
            gracedb.client.addEventToSuperevent.assert_called_with(
                superevent_id, graceid)
    if graceid.startswith('S'):
        gracedb.client.addEventToSuperevent.assert_has_calls([
             call(graceid, exttrig['graceid'])
             for exttrig in raven_search_results])


def mock_get_event(exttrig_id):
    if exttrig_id == 'E1':
        return {'search': 'GRB'}
    elif exttrig_id == 'E2':
        return {'search': 'SNEWS'}
    elif exttrig_id == 'E3':
        return {'search': 'GRB'}
    else:
        raise RuntimeError('Asked for search of unexpected exttrig')


@pytest.mark.parametrize('group', ['CBC', 'Burst'])
@patch('gwcelery.tasks.gracedb.get_event', mock_get_event)
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'em_events': ['E1', 'E2', 'E3']})
@patch('gwcelery.tasks.raven.calc_signif')
@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
def test_calculate_coincidence_far(
        mock_se_cls, mock_exttrig_cls, mock_calc_signif,
        mock_get_superevent, group):
    raven.calculate_coincidence_far('S1234', group).delay().get()


@pytest.mark.parametrize('group', ['CBC', 'Burst'])  # noqa: F811
@patch('gwcelery.tasks.gracedb.download')
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'em_events': ['E1', 'E2', 'E3']})
@patch('gwcelery.tasks.ligo_fermi_skymaps.get_preferred_skymap',
       return_value='bayestar.fits.gz')
@patch('gwcelery.tasks.raven.calc_signif')
@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
def test_calculate_spacetime_coincidence_far(
        mock_se_cls, mock_exttrig_cls, mock_calc_signif,
        mock_get_preferred_skymap, mock_get_superevent, mock_download, group,
        toy_fits_filecontents):
    mock_download.return_value = toy_fits_filecontents
    raven.calculate_spacetime_coincidence_far(
        'S1234', group).delay().get()


@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
@patch('ligo.raven.search.calc_signif_gracedb')
def test_calc_signif(
        mock_raven_calc_signif, mock_se_cls, mock_exttrig_cls):
    se = mock_se_cls('S1', gracedb=gracedb.client)
    exttrig = mock_exttrig_cls('E1', gracedb=gracedb.client)
    tl, th = -1, 5
    raven.calc_signif(se, exttrig, tl, th, incl_sky=False)

    mock_raven_calc_signif.assert_called_once_with(
        se, exttrig, tl, th, incl_sky=False)


@patch('ligo.raven.gracedb_events.ExtTrig')
@patch('ligo.raven.gracedb_events.SE')
@patch('ligo.raven.search.calc_signif_gracedb')
def test_calc_signif_skymaps(
        mock_raven_calc_signif, mock_se_cls, mock_exttrig_cls):
    se = mock_se_cls('S1', fitsfile='bayestar.fits.gz', gracedb=gracedb.client)
    exttrig = mock_exttrig_cls('E1', gracedb=gracedb.client)
    tl, th = -1, 5
    raven.calc_signif(se, exttrig, tl, th, incl_sky=True)

    mock_raven_calc_signif.assert_called_once_with(
        se, exttrig, tl, th, incl_sky=True)


@pytest.mark.parametrize('graceid,group', [['E1', 'CBC'], ['S1', 'CBC'],
                                           ['E1', 'Burst'], ['S1', 'Burst']])
@patch('gwcelery.tasks.raven.search')
@patch('gwcelery.tasks.raven.add_exttrig_to_superevent')
def test_coincidence_search(mock_add_exttrig, mock_raven_search,
                            graceid, group):
    raven.coincidence_search(graceid, {'superevent_id': graceid},
                             group).delay().get()
