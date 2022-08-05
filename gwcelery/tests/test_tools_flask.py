from unittest.mock import Mock

from .. import main, app as celery_app
from ..tools import flask


def test_flask_run(monkeypatch):
    """Test starting the Flask server from the command line."""
    mock_run_simple = Mock()
    monkeypatch.setattr('flask.cli.run_simple', mock_run_simple)
    monkeypatch.setenv('FLASK_RUN_PORT', '5556')
    monkeypatch.setattr(celery_app.log, 'setup', Mock())

    main(['gwcelery', 'flask', 'run'])

    mock_run_simple.assert_called_once()
    args, kwargs = mock_run_simple.call_args
    host, port, app = args
    assert host == '127.0.0.1'
    assert port == 5556
    assert app == flask.app
