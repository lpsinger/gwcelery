import pkg_resources
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

import pytest

from ..tasks.bayestar import bayestar_localize

pytest.importorskip('lalinference.bayestar.sky_map')


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_bayestar_localize_bad_psd(mock_gracedb):
    """Test running BAYESTAR with a pad PSD file"""
    from xml.sax import SAXParseException

    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = ''

    # Run function under test
    with pytest.raises(SAXParseException):
        bayestar_localize(
            (coinc, psd), 'G211117', 'https://gracedb.invalid/api/')


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_bayestar_localize(mock_gracedb):
    """Test running BAYESTAR on G211117"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = bayestar_localize(
        (coinc, psd), 'G211117', 'https://gracedb.invalid/api/')

    # FIXME: should do some sanity checks of the sky map here


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_bayestar_localize_detector_disabled(mock_gracedb):
    """Test running BAYESTAR on G211117 with L1 disabled"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = bayestar_localize(
        (coinc, psd), 'G211117', 'https://gracedb.invalid/api/',
        disabled_detectors=['L1'])

    # FIXME: should do some sanity checks of the sky map here
