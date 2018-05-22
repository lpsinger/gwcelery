import io
from unittest.mock import patch

from glue.ligolw import utils
from glue.ligolw import lsctables
from glue.ligolw import table
from ligo.skymap.io.events.ligolw import ContentHandler
import pkg_resources
import pytest

from ..tasks.first2years import pick_coinc, upload_event

pytest.importorskip('lal')


def mock_now():
    import lal
    return lal.LIGOTimeGPS(1208808586)


@patch('lal.GPSTimeNow', mock_now)
def test_pick_coinc():
    coinc = pick_coinc()
    xmldoc, _ = utils.load_fileobj(io.BytesIO(coinc),
                                   contenthandler=ContentHandler)

    coinc_inspiral_table = table.get_table(
        xmldoc, lsctables.CoincInspiralTable.tableName)

    assert len(coinc_inspiral_table) == 1
    coinc_inspiral, = coinc_inspiral_table
    assert coinc_inspiral.get_end() <= mock_now()


@patch('lal.GPSTimeNow', mock_now)
@patch('gwcelery.tasks.gracedb.create_event', return_value='M1234')
@patch('gwcelery.tasks.gracedb.upload')
def test_upload_event(mock_upload, mock_create_event):
    coinc = pick_coinc()
    psd = pkg_resources.resource_filename(
        __name__, '../data/first2years/2016/psd.xml.gz')
    with open(psd, 'rb') as f:
        psd = f.read()

    upload_event()
    mock_create_event.assert_called_once_with(coinc, 'MDC', 'gstlal', 'CBC')
    mock_upload.assert_called_once_with(
        psd, 'psd.xml.gz', 'M1234', 'Noise PSD', ['psd'])
