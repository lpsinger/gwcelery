from unittest.mock import Mock, patch

from ligo.gracedb import rest
import pkg_resources
import pytest

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


@pytest.mark.parametrize(
    'group,other_group,annotate,other_annotate', [
        [
            'CBC', 'Burst',
            'gwcelery.tasks.orchestrator.annotate_cbc_superevent.run',
            'gwcelery.tasks.orchestrator.annotate_burst_superevent.run'
        ],
        [
            'Burst', 'CBC',
            'gwcelery.tasks.orchestrator.annotate_burst_superevent.run',
            'gwcelery.tasks.orchestrator.annotate_cbc_superevent.run'
        ]
    ])
def test_handle_superevent(monkeypatch, group, other_group,
                           annotate, other_annotate):
    """Test a superevent is dispatched to the correct annotation task based on
    its preferred event's search group."""
    alert = {
        'alert_type': 'new',
        'object': {
            'superevent_id': 'S1234',
            't_start': 1214714160,
            't_end': 1214714164
        }
    }

    def get_superevent(superevent_id):
        assert superevent_id == 'S1234'
        return {'preferred_event': 'G1234'}

    def get_event(graceid):
        assert graceid == 'G1234'
        return {'group': group, 'search': 'CBC', 'instruments': 'H1,L1,V1'}

    mock_annotate = Mock()
    mock_other_annotate = Mock()

    monkeypatch.setattr('gwcelery.tasks.gracedb.get_superevent.run',
                        get_superevent)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_event.run',
                        get_event)
    monkeypatch.setattr(annotate, mock_annotate)
    monkeypatch.setattr(other_annotate, mock_other_annotate)

    # Run function under test
    orchestrator.handle_superevent(alert)

    mock_annotate.assert_called_once_with(get_event('G1234'), 'S1234')

    # FIXME: The assertion below will fail in the unit tests because of an
    # issue in Celery with Ignore semipredicates in eager mode. However, it
    # is fine when running live.
    # See https://github.com/celery/celery/issues/4868.

    # mock_other_annotate.assert_not_called()


def mock_download(filename, graceid, *args, **kwargs):
    assert graceid == 'T250822'
    if filename == 'coinc.xml':
        return pkg_resources.resource_string(__name__, 'data/coinc.xml')
    elif filename == 'psd.xml.gz':
        return pkg_resources.resource_string(__name__, 'data/psd.xml.gz')
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier.run')
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event(mock_gracedb, mock_localize, mock_classifier):
    """Test that an LVAlert message for a newly uploaded PSD file triggers
    BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_psd.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_called_once()
    mock_classifier.assert_called_once()


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.em_bright.classifier.run')
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_cbc_event_ignored(mock_gracedb, mock_localize,
                                  mock_classifier):
    """Test that unrelated LVAlert messages do not trigger BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_detchar.json')
    orchestrator.handle_cbc_event(alert)
    mock_localize.assert_not_called()
    mock_classifier.assert_not_called()


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
