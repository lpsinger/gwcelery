from unittest.mock import Mock, call

import pytest

from ..tasks import gracedb, raven


@pytest.mark.parametrize(
    'event_type,event_id', [['SE', 'S1234'], ['ExtTrig', 'E1234']])
def test_raven_search(monkeypatch, event_type, event_id):
    """Test that correct input parameters are used for raven."""
    alert_object = {}
    if event_type == 'SE':
        alert_object['superevent_id'] = event_id

    mock_exttrig_object = Mock()
    mock_se_object = Mock()
    mock_search = Mock()

    monkeypatch.setattr('ligo.raven.search.search', mock_search)
    monkeypatch.setattr('ligo.raven.gracedb_events.SE', mock_se_object)
    monkeypatch.setattr('ligo.raven.gracedb_events.ExtTrig',
                        mock_exttrig_object)

    # call raven search
    raven.search(event_id, alert_object)
    if event_id == 'S1234':
        mock_search.assert_called_once_with(
            mock_se_object(event_id, gracedb=gracedb.client), -5, 5,
            gracedb=gracedb.client, group=None)
    elif event_id == 'E1234':
        mock_search.assert_called_once_with(
            mock_exttrig_object(event_id, gracedb=gracedb.client), -5, 5,
            gracedb=gracedb.client, group=None)
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
