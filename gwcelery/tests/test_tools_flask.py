from unittest.mock import Mock

import pytest

from .. import app as celery_app
from ..tools import flask


def test_flask_run(monkeypatch):
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
