from unittest.mock import patch
from xml.sax import SAXParseException

from astropy import table
from astropy.io import fits
from celery.exceptions import Ignore
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


def mock_bayestar(event, *args, **kwargs):
    # Attempt to access single-detector triggers, so that a
    # DetectorDisabledError may be raised
    event.singles

    return table.Table({'UNIQ': np.arange(4, 16, dtype=np.uint64),
                        'PROBDENSITY': np.ones(12),
                        'DISTMU': np.ones(12),
                        'DISTSIGMA': np.ones(12),
                        'DISTNORM': np.ones(12)})


@pytest.fixture
def coinc_psd():
    return (pkg_resources.resource_string(__name__, 'data/coinc.xml'),
            pkg_resources.resource_string(__name__, 'data/psd.xml.gz'))


@patch('ligo.skymap.bayestar.localize', mock_bayestar)
def test_localize(coinc_psd):
    """Test running BAYESTAR on G211117"""
    fitscontent = localize(coinc_psd, 'G211117')
    with NamedTemporaryFile(content=fitscontent) as fitsfile:
        url = fits.getval(fitsfile.name, 'REFERENC', 1)
        assert url == 'https://gracedb.invalid/events/G211117'


@patch('ligo.skymap.bayestar.localize', mock_bayestar)
def test_localize_all_detectors_disabled(coinc_psd):
    """Test running BAYESTAR on G211117, all detectors disabled"""
    with pytest.raises(Ignore):
        localize(coinc_psd, 'G211117', disabled_detectors=['H1', 'L1', 'V1'])
