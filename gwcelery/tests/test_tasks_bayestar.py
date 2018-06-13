from unittest.mock import patch
from xml.sax import SAXParseException

from astropy import table
from ligo.gracedb import rest
import numpy as np
import pkg_resources
import pytest

from ..tasks.bayestar import handle, localize
from . import resource_json


def mock_download(filename, graceid, *args, **kwargs):
    assert graceid == 'T250822'
    if filename == 'coinc.xml':
        return pkg_resources.resource_string(__name__, 'data/coinc.xml')
    elif filename == 'psd.xml.gz':
        return pkg_resources.resource_string(__name__, 'data/psd.xml.gz')
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle(mock_gracedb, mock_localize):
    """Test that an LVAlert message for a newly uploaded PSD file triggers
    BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_psd.json')
    handle(alert)
    mock_localize.assert_called_once()


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.bayestar.localize.run')
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_handle_ignored(mock_gracedb, mock_localize):
    """Test that unrelated LVAlert messages do not trigger BAYESTAR."""
    alert = resource_json(__name__, 'data/lvalert_detchar.json')
    handle(alert)
    mock_localize.assert_not_called()


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_localize_bad_psd(mock_gracedb):
    """Test running BAYESTAR with a pad PSD file"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = b''

    # Run function under test
    with pytest.raises(SAXParseException):
        localize((coinc, psd), 'G211117')


def mock_bayestar(*args, **kwargs):
    return table.Table({'UNIQ': np.arange(4, 16, dtype=np.uint64),
                        'PROBDENSITY': np.ones(12),
                        'DISTMU': np.ones(12),
                        'DISTSIGMA': np.ones(12),
                        'DISTNORM': np.ones(12)})


@pytest.mark.parametrize('disabled_detectors', [None,
                                                ['H1', 'L1'],
                                                ['H1', 'L1', 'V1']])
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
@patch('ligo.skymap.bayestar.localize', mock_bayestar)
def test_localize(mock_gracedb, disabled_detectors):
    """Test running BAYESTAR on G211117"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = localize(
        (coinc, psd), 'G211117', disabled_detectors=disabled_detectors)

    # FIXME: should do some sanity checks of the sky map here
    assert fitscontent
