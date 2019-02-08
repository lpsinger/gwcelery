import datetime
from unittest.mock import Mock

from flask import get_flashed_messages, url_for
from ligo.gracedb.rest import HTTPError as GraceDbHTTPError
import pytest
from werkzeug.http import HTTP_STATUS_CODES

from .. import app as celery_app
from .. import flask


@pytest.fixture
def app():
    return flask.app


def test_command(monkeypatch):
    """Test starting the Flask server from the command line."""
    mock_run_simple = Mock()
    monkeypatch.setattr('werkzeug.serving.run_simple', mock_run_simple)
    monkeypatch.setenv('FLASK_PORT', '5556')

    with pytest.raises(SystemExit) as excinfo:
        celery_app.start(['gwcelery', 'flask', 'run', '--eager-loading'])

    assert excinfo.value.code == 0
    mock_run_simple.assert_called_once()
    args, kwargs = mock_run_simple.call_args
    host, port, loader = args
    assert host == '127.0.0.1'
    assert port == 5556
    assert loader._app == flask.app


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
        'source_classification_filename': 'source_classification.json',
        'p_astro_filename': 'p_astro.json'})

    assert HTTP_STATUS_CODES[response.status_code] == 'Found'
    assert get_flashed_messages() == [
        'Queued update alert for MS190208a.']
    mock_update_alert.assert_called_once_with(
        'MS190208a', 'bayestar.fits.gz',
        'source_classification.json', 'p_astro.json')


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
    """Test that the typeahead endpoints return an empty list if GraceDb
    returns a 404 error."""
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs',
                        Mock(side_effect=GraceDbHTTPError(404, None, None)))

    response = client.get(
        url_for('typeahead_skymap_filename', superevent_id='MS190208a'))

    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    assert response.json == []


def test_typeahead_skymap_filename_gracedb_error_non_404(client, monkeypatch):
    """Test that the typeahead raises an internal error if GraceDb
    returns an error other than 404."""
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs',
                        Mock(side_effect=GraceDbHTTPError(403, None, None)))

    response = client.get(
        url_for('typeahead_skymap_filename', superevent_id='MS190208a'))

    assert HTTP_STATUS_CODES[response.status_code] == 'Internal Server Error'


@pytest.mark.parametrize('endpoint,tag', [
    ('typeahead_source_classification_filename', 'em_bright'),
    ('typeahead_p_astro_filename', 'p_astro')
])
def test_typeahead_source_classification_and_p_astro(
        endpoint, tag, client, monkeypatch):
    """Test typeahead filtering for source_classification and p_astro files."""
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
