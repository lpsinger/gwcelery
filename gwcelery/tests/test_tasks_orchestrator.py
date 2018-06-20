# import json
from unittest.mock import patch

from celery import group

from ..tasks import orchestrator
from . import resource_json


@patch('gwcelery.tasks.circulars.create_circular')
@patch('gwcelery.tasks.skymaps.annotate_fits')
@patch('gwcelery.tasks.bayestar.bayestar')
@patch('gwcelery.tasks.gcn.send.delay')
def test_handle_voevent(mock_send, mock_bayestar, mock_annotate_fits,
                        mock_create_circular):
    """Test dispatch of a VOEvent message."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_voevent.json')

    # text = alert['object']['text']

    # Run function under test
    orchestrator.handle(alert)

    # Check that the correct tasks were dispatched.
    mock_annotate_fits.assert_not_called()
    mock_bayestar.assert_not_called()
    mock_create_circular.assert_not_called()
    # FIXME: temporarily disable sending GCNs as per P. Brady request
    mock_send.assert_not_called()  # mock_send.assert_called_once_with(text)


@patch('gwcelery.tasks.circulars.create_circular')
@patch('gwcelery.tasks.skymaps.annotate_fits')
@patch('gwcelery.tasks.bayestar.bayestar')
def test_handle_label(mock_bayestar, mock_annotate_fits, mock_create_circular):
    """Test dispatch of a label message that should be ignored."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_label_dqv.json')

    # Run function under test
    orchestrator.handle(alert)

    # Check that no tasks were dispatched.
    mock_annotate_fits.assert_not_called()
    mock_bayestar.assert_not_called()
    mock_create_circular.assert_not_called()


@patch('gwcelery.tasks.circulars.create_circular')
@patch('gwcelery.tasks.skymaps.annotate_fits')
@patch('gwcelery.tasks.bayestar.bayestar')
def test_handle_ignored(mock_bayestar, mock_annotate_fits,
                        mock_create_circular):
    """Test dispatch of a detchar status message that should be ignored."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_detchar.json')

    # Run function under test
    orchestrator.handle(alert)

    # Check that no tasks were dispatched.
    mock_annotate_fits.assert_not_called()
    mock_bayestar.assert_not_called()
    mock_create_circular.assert_not_called()


@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.circulars.create_circular.run')
@patch('gwcelery.tasks.bayestar.bayestar', return_value=group())
def test_handle_psd(mock_bayestar, mock_create_circular, mock_upload):
    """Test dispatch of an LVAlert message for a PSD upload."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_psd.json')

    # Run function under test
    orchestrator.handle(alert)

    # Check that the correct tasks were dispatched.
    mock_bayestar.assert_called_once_with('T250822')
    mock_create_circular.assert_called_once_with('T250822')
    mock_upload.assert_called_once()


@patch('gwcelery.tasks.skymaps.annotate_fits')
def test_handle_fits(mock_annotate_fits):
    """Test dispatch of an LVAlert message for a PSD upload."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_fits.json')

    # Run function under test
    orchestrator.handle(alert)

    # Check that the correct tasks were dispatched.
    mock_annotate_fits.assert_called_once_with(
        'bayestar.fits.gz,2', 'bayestar', 'T250822', ['sky_loc'])


@patch('gwcelery.tasks.raven.coincidence_search')
def test_handle_superevent_creation(mock_raven_coincidence_search):
    """Test dispatch of an LVAlert message for a superevent creation."""
    # Test LVAlert payload.
    alert = resource_json(__name__, 'data/lvalert_superevent_creation.json')

    # Run function under test
    orchestrator.handle_superevents_externaltriggers(alert)

    # Check that the correct tasks were dispatched.
    mock_raven_coincidence_search.assert_called_once_with('S180616h',
                                                          alert['object'])
