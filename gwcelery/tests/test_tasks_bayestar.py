from unittest.mock import patch
from xml.sax import SAXParseException

from astropy import table
import numpy as np
import pkg_resources
import pytest

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


def mock_bayestar(*args, **kwargs):
    return table.Table({'UNIQ': np.arange(4, 16, dtype=np.uint64),
                        'PROBDENSITY': np.ones(12),
                        'DISTMU': np.ones(12),
                        'DISTSIGMA': np.ones(12),
                        'DISTNORM': np.ones(12)})


@pytest.mark.parametrize('disabled_detectors', [None, ['L1']])
@patch('ligo.gracedb.rest.GraceDb', autospec=True)
@patch('ligo.skymap.bayestar.localize', mock_bayestar)
def test_localize(mock_gracedb, disabled_detectors):
    """Test running BAYESTAR on G211117"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = localize(
        (coinc, psd), 'G211117', 'https://gracedb.invalid/api/',
        disabled_detectors=disabled_detectors)

    # FIXME: should do some sanity checks of the sky map here
    assert fitscontent
