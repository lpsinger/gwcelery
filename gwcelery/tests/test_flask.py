from unittest.mock import Mock

from flask import get_flashed_messages, url_for
from werkzeug.http import HTTP_STATUS_CODES
import pytest

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
