from unittest.mock import patch
import pkg_resources
import pytest
from xml.sax import SAXParseException

from ..tasks.bayestar import bayestar, localize


def mock_download(filename, graceid, service):
    assert graceid == 'T12345'
    assert service == 'https://gracedb.invalid/api/'
    if filename == 'coinc.xml':
        return pkg_resources.resource_string(__name__, 'coinc.xml')
    elif filename == 'psd.xml.gz':
        return pkg_resources.resource_string(__name__, 'psd.xml.gz')
    else:
        raise ValueError


@patch('gwcelery.tasks.gracedb.download', mock_download)
@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_bayestar(mock_gracedb):
    # Run function under test
    bayestar('T12345', 'https://gracedb.invalid/api/')


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_localize_bad_psd(mock_gracedb):
    """Test running BAYESTAR with a pad PSD file"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = b''

    # Run function under test
    with pytest.raises(SAXParseException):
        localize(
            (coinc, psd), 'G211117', 'https://gracedb.invalid/api/')


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_localize(mock_gracedb):
    """Test running BAYESTAR on G211117"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = localize(
        (coinc, psd), 'G211117', 'https://gracedb.invalid/api/')

    # FIXME: should do some sanity checks of the sky map here
    assert fitscontent


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_localize_detector_disabled(mock_gracedb):
    """Test running BAYESTAR on G211117 with L1 disabled"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = localize(
        (coinc, psd), 'G211117', 'https://gracedb.invalid/api/',
        disabled_detectors=['L1'])

    # FIXME: should do some sanity checks of the sky map here
    assert fitscontent
