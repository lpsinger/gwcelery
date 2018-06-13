from unittest.mock import patch

from ..tasks import orchestrator
from . import resource_json


# @patch('gwcelery.tasks.circulars.create_circular')
# @patch('gwcelery.tasks.skymaps.annotate_fits')
# @patch('gwcelery.tasks.bayestar.bayestar')
# @patch('gwcelery.tasks.gcn.send.delay')
# def test_handle_voevent(mock_send, mock_bayestar, mock_annotate_fits,
#                         mock_create_circular):
#     """Test dispatch of a VOEvent message."""
#     # Test LVAlert payload.
#     alert = resource_json(__name__, 'data/lvalert_voevent.json')
#
#     # text = alert['object']['text']
#
#     # Run function under test
#     orchestrator.handle(alert)
#
#     # Check that the correct tasks were dispatched.
#     mock_annotate_fits.assert_not_called()
#     mock_bayestar.assert_not_called()
#     mock_create_circular.assert_not_called()
#     # FIXME: temporarily disable sending GCNs as per P. Brady request
#     mock_send.assert_not_called()  # mock_send.assert_called_once_with(text)


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
