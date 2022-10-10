import io
from unittest.mock import call, patch

from ligo.lw import utils
from ligo.lw import lsctables
from ligo.skymap.io.events.ligolw import ContentHandler
import pytest

from .. import app
from ..tasks.first2years import pick_coinc, upload_event

pytest.importorskip('lal')


def mock_now():
    import lal
    return lal.LIGOTimeGPS(1208808586)


@patch('lal.GPSTimeNow', mock_now)
def test_pick_coinc():
    coinc = pick_coinc()
    xmldoc = utils.load_fileobj(io.BytesIO(coinc),
                                contenthandler=ContentHandler)

    coinc_inspiral_table = lsctables.CoincInspiralTable.get_table(xmldoc)

    assert len(coinc_inspiral_table) == 1
    coinc_inspiral, = coinc_inspiral_table
    assert coinc_inspiral.end <= mock_now()


@patch('lal.GPSTimeNow', mock_now)
@patch('gwcelery.tasks.gracedb.create_event.run',
       return_value={'graceid': 'M1234'})
@patch('gwcelery.tasks.gracedb.get_superevents.run',
       return_value=[{'superevent_id': 'S1234'}])
@patch('gwcelery.tasks.gracedb.create_signoff.run')
def test_upload_event(mock_create_signoff, mock_get_superevents,
                      mock_create_event):
    num = 16 if app.conf['mock_events_simulate_multiple_uploads'] else 1
    coinc = pick_coinc()

    upload_event()

    mock_create_event.has_calls(
            [call(coinc, 'MDC', 'gstlal', 'CBC') for count in range(num)])
    mock_get_superevents.assert_called_once_with('MDC event: M1234')
    mock_create_signoff.assert_called_once()
    msg = ('If this had been a real gravitational-wave event candidate, '
           'then an on-duty scientist would have left a comment here on '
           'data quality and the status of the detectors.')
    assert mock_create_signoff.call_args in (
        call('NO', msg, 'ADV', 'S1234'), call('OK', msg, 'ADV', 'S1234'))
