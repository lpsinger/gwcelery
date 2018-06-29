from unittest.mock import patch
from xml.sax import SAXParseException

from astropy import table
from astropy.io import fits
import numpy as np
import pkg_resources
import pytest

from ..tasks.bayestar import localize
from ..util.tempfile import NamedTemporaryFile


def test_localize_bad_psd():
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
@patch('ligo.skymap.bayestar.localize', mock_bayestar)
def test_localize(disabled_detectors):
    """Test running BAYESTAR on G211117"""
    # Test data
    coinc = pkg_resources.resource_string(__name__, 'data/coinc.xml')
    psd = pkg_resources.resource_string(__name__, 'data/psd.xml.gz')

    # Run function under test
    fitscontent = localize(
        (coinc, psd), 'G211117', disabled_detectors=disabled_detectors)

    with NamedTemporaryFile(content=fitscontent) as fitsfile:
        url = fits.getval(fitsfile.name, 'REFERENC', 1)
        assert url == 'https://gracedb.invalid/events/G211117'
