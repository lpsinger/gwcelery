from unittest.mock import Mock

from ..tasks import circulars
from ..tasks import legacy_gracedb as gracedb


def test_create_initial_circular(monkeypatch):
    """Test that the compose circulars method is called with the correct
    input parameters.
    """
    superevent_id = 'S1234'
    mock_compose = Mock()
    monkeypatch.setattr('ligo.followup_advocate.compose', mock_compose)

    # call create_initial_circular
    circulars.create_initial_circular(superevent_id)
    mock_compose.assert_called_once_with('S1234', client=gracedb.client)


def test_create_emcoinc_circular(monkeypatch):
    """Test that the compose emcoinc circulars method is called with the
    correct input parameters.
    """
    superevent_id = 'S1234'
    mock_compose_emcoinc_circular = Mock()
    monkeypatch.setattr('ligo.followup_advocate.compose_raven',
                        mock_compose_emcoinc_circular)

    # call create_emcoinc_circular
    circulars.create_emcoinc_circular(superevent_id)
    mock_compose_emcoinc_circular.assert_called_once_with(
        'S1234', client=gracedb.client)


def test_create_retraction_circular(monkeypatch):
    """Test that the compose retraction circulars method is called with
    the correct input parameters.
    """
    superevent_id = 'S1234'
    mock_compose_retraction = Mock()
    monkeypatch.setattr('ligo.followup_advocate.compose_retraction',
                        mock_compose_retraction)

    # call create_retraction_circular
    circulars.create_retraction_circular(superevent_id)
    mock_compose_retraction.assert_called_once_with(
        'S1234', client=gracedb.client)
