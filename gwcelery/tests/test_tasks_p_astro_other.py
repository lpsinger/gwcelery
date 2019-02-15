import json
from urllib import request
from unittest.mock import patch

import pytest

from ..tasks import p_astro_other


class MockResponse(object):
    def read(self):
        return json.dumps({
            "counts_BNS": 2,
            "counts_BBH": 10,
            "counts_NSBH": 1,
            "counts_Terrestrial": 4000,
            "counts_MassGap": 1})

    def close(self):
        pass


@pytest.mark.parametrize(
    'snr,far,mass1,mass2', ([30., 1e-17, 1.4, 1.4],
                            [100, 1e-10, 400, 40]))
@patch.object(request, 'urlopen', return_value=MockResponse())
def test_compute_p_astro(mock_response, snr, far, mass1, mass2):
    """Check if p_astros sum up to unity"""
    p_astros = json.loads(
        p_astro_other.compute_p_astro(snr, far, mass1, mass2))
    assert pytest.approx(sum(p_astros.values())) == 1.


@patch.object(request, 'urlopen', return_value=MockResponse())
def test_compute_p_astro_bns(mock_response):
    """Test p_astro values with CBC catalog paper
    values for GW170817
    """
    # values based on G322759
    snr = 33.
    far = 7.6e-59
    mass1 = 1.77
    mass2 = 1.07

    p_astros = json.loads(
        p_astro_other.compute_p_astro(snr, far, mass1, mass2))
    assert pytest.approx(p_astros['BNS']) == 1.
