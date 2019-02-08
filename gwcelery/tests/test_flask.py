from unittest.mock import patch

import pytest

from .. import app
from .. import flask


@patch('werkzeug.serving.run_simple')
def test_flask_command(mock_run_simple):
    """Test starting the Flask server from the command line."""
    with pytest.raises(SystemExit) as excinfo:
        app.start(['gwcelery', 'flask', 'run', '--eager-loading'])
    assert excinfo.value.code == 0
    mock_run_simple.assert_called_once()
    assert mock_run_simple.call_args[0][2]._app == flask.app
