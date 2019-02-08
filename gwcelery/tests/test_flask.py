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


def test_typeahead_skymap_filename_gracedb_404(client, monkeypatch):
    """Test that the typeahead endpoints return an empty list if GraceDb
    returns a 404 error."""
    monkeypatch.setattr('gwcelery.tasks.gracedb.client.logs',
                        Mock(side_effect=GraceDbHTTPError(404, None, None)))

    response = client.get(
        url_for('typeahead_skymap_filename', superevent_id='MS190208a'))

    assert HTTP_STATUS_CODES[response.status_code] == 'OK'
    assert response.json == []


@pytest.mark.parametrize('endpoint,tag', [
    ('typeahead_source_classification_filename', 'em_bright'),
    ('typeahead_p_astro_filename', 'p_astro')
])
def test_typeahead(endpoint, tag, client, monkeypatch):
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
