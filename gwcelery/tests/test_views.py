import datetime
from unittest.mock import Mock

from flask import get_flashed_messages, url_for
from ligo.gracedb.rest import HTTPError as GraceDbHTTPError
import pytest
from werkzeug.http import HTTP_STATUS_CODES

from .. import flask
from .. import views as _  # noqa: F401


@pytest.fixture
def app():
    return flask.app


def test_send_preliminary_gcn_post_no_data(client, monkeypatch):
    """Test send_update_gcn endpoint with no form data."""
    mock_update_superevent = Mock()
    mock_get_event = Mock()
    mock_preliminary_alert = Mock()
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.update_superevent.run',
        mock_update_superevent)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.get_event.run',
        mock_get_event)
    monkeypatch.setattr(
        'gwcelery.tasks.orchestrator.preliminary_alert.run',
        mock_preliminary_alert)

    response = client.post(url_for('send_preliminary_gcn'))
    assert HTTP_STATUS_CODES[response.status_code] == 'Found'
    assert get_flashed_messages() == [
        'No alert sent. Please fill in all fields.']
    mock_update_superevent.assert_not_called()
    mock_get_event.assert_not_called()
    mock_preliminary_alert.assert_not_called()


def test_send_preliminary_gcn_post(client, monkeypatch):
    """Test send_update_gcn endpoint with complete form data."""
    mock_update_superevent = Mock()
    mock_event = Mock()
    mock_get_event = Mock(return_value=mock_event)
    mock_preliminary_alert = Mock()
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.update_superevent.run',
        mock_update_superevent)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.get_event.run',
        mock_get_event)
    monkeypatch.setattr(
        'gwcelery.tasks.orchestrator.preliminary_alert.run',
        mock_preliminary_alert)

    response = client.post(url_for('send_preliminary_gcn'), data={
        'superevent_id': 'MS190208a',
        'event_id': 'M12345'})
    assert HTTP_STATUS_CODES[response.status_code] == 'Found'
    assert get_flashed_messages() == [
        'Queued preliminary alert for MS190208a.']
    mock_update_superevent.assert_called_once_with(
        'MS190208a', preferred_event='M12345')
    mock_get_event.assert_called_once_with('M12345')
    mock_preliminary_alert.assert_called_once_with(mock_event, 'MS190208a')


def test_send_update_gcn_get(client):
    """Test send_update_gcn endpoint with disallowed HTTP method."""
    # GET requests not allowed
    response = client.get(url_for('send_update_gcn'))
    assert HTTP_STATUS_CODES[response.status_code] == 'Method Not Allowed'


def test_send_update_gcn_post_no_data(client):
    """Test send_update_gcn endpoint with no form data."""
    response = client.post(url_for('send_update_gcn'))
    assert HTTP_STATUS_CODES[response.status_code] == 'Found'
    assert get_flashed_messages() == [
        'No alert sent. Please fill in all fields.']


def test_send_update_gcn_post(client, monkeypatch):
    """Test send_update_gcn endpoint with complete form data."""
    mock_update_alert = Mock()
    monkeypatch.setattr(
        'gwcelery.tasks.orchestrator.update_alert.run', mock_update_alert)

    response = client.post(url_for('send_update_gcn'), data={
        'superevent_id': 'MS190208a',
        'skymap_filename': 'bayestar.fits.gz',
        'em_bright_filename': 'em_bright.json',
        'p_astro_filename': 'p_astro.json'})

    assert HTTP_STATUS_CODES[response.status_code] == 'Found'
    assert get_flashed_messages() == [
        'Queued update alert for MS190208a.']
    mock_update_alert.assert_called_once_with(
        'MS190208a', 'bayestar.fits.gz',
        'em_bright.json', 'p_astro.json')


def test_typeahead_superevent_id(client, monkeypatch):
    """Test typeahead filtering for superevent_id."""
    mock_superevents = Mock(return_value=(
        {
            'superevent_id': (
                datetime.date(2019, 2, 1) + datetime.timedelta(i)
            ).strftime('MS%y%m%da')
        } for i in range(31)))
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.client.superevents', mock_superevents)

    response = client.get(
        url_for('typeahead_superevent_id', superevent_id='MS1902'))

    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    assert response.json == [
        'MS190201a', 'MS190202a', 'MS190203a', 'MS190204a', 'MS190205a',
        'MS190206a', 'MS190207a', 'MS190208a']


def test_typeahead_superevent_id_invalid_date(client, monkeypatch):
    """Test typeahead filtering for superevent_id when the search term contains
    an invalid date fragment."""
    mock_superevents = Mock()
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.client.superevents', mock_superevents)

    response = client.get(
        url_for('typeahead_superevent_id', superevent_id='MS190235'))

    mock_superevents.assert_not_called()
    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    assert response.json == []


def test_typeahead_skymap_filename_gracedb_error_404(client, monkeypatch):
    """Test that the typeahead endpoints return an empty list if GraceDB
    returns a 404 error."""
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs',
                        Mock(side_effect=GraceDbHTTPError(404, None, None)))

    response = client.get(
        url_for('typeahead_skymap_filename', superevent_id='MS190208a'))

    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    assert response.json == []


def test_typeahead_skymap_filename_gracedb_error_non_404(client, monkeypatch):
    """Test that the typeahead raises an internal error if GraceDB
    returns an error other than 404."""
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs',
                        Mock(side_effect=GraceDbHTTPError(403, None, None)))

    response = client.get(
        url_for('typeahead_skymap_filename', superevent_id='MS190208a'))

    assert HTTP_STATUS_CODES[response.status_code] == 'Internal Server Error'


@pytest.mark.parametrize('endpoint,tag', [
    ('typeahead_em_bright_filename', 'em_bright'),
    ('typeahead_p_astro_filename', 'p_astro')
])
def test_typeahead_em_bright_and_p_astro(
        endpoint, tag, client, monkeypatch):
    """Test typeahead filtering for em_bright and p_astro files."""
    mock_logs = Mock()
    mock_logs.configure_mock(**{'return_value.json.return_value': {'log': [
        {'filename': 'foobar.txt', 'tag_names': [tag]},
        {'filename': 'bar.json', 'tag_names': [tag]},
        {'filename': 'foobar.json', 'tag_names': [tag]},
        {'filename': 'foobat.json', 'tag_names': [tag]},
        {'filename': 'foobaz.json', 'tag_names': ['wrong_tag']}]}})
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs', mock_logs)

    response = client.get(
        url_for(endpoint, superevent_id='MS190208a', filename='foo'))

    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    mock_logs.assert_called_once_with('MS190208a')
    assert response.json == ['foobar.json', 'foobat.json']
