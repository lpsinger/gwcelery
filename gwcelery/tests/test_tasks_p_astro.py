import json

import pytest

from ..tasks import p_astro


@pytest.mark.parametrize(
    'snr,far,mass1,mass2,pipeline,instruments',
    ([30., 1e-17, 1.4, 1.4, 'mbta', {'H1', 'L1', 'V1'}],
     [100, 3e-10, 400, 40, 'mbta', {'H1', 'L1'}],
     [10, 3e-10, 20, 30, 'pycbc', {'L1', 'V1'}]))
def test_compute_p_astro(snr, far, mass1, mass2,
                         pipeline, instruments):
    """Check if p_astros sum up to unity"""
    p_astros = json.loads(
        p_astro.compute_p_astro(snr, far, mass1, mass2,
                                pipeline, instruments))
    assert (
        set(p_astros) - set({'BNS', 'Terrestrial', 'NSBH', 'BBH'})
    ) == set()
    assert pytest.approx(sum(p_astros.values())) == 1.


@pytest.mark.parametrize(
    'far,pipeline,instruments,snr_thresh,val',
    ([1e-25, 'mbta', {'H1', 'L1', 'V1'}, 12, 1],
     [1e-8, 'mbta', {'L1', 'V1'}, 33, 0.08],
     [6e-10, 'mbta', {'H1', 'V1'}, 10, 0.99],
     [7.6e-59, 'spiir', {'H1', 'L1', 'V1'}, 33, 1],
     [1e-10, 'pycbc', {'H1', 'L1'}, 10, 1],
     [1e-10, 'pycbc', {'H1', 'L1', 'V1'}, 10, 1]))
def test_compute_p_astro_bns(far, pipeline, instruments,
                             snr_thresh, val):
    """Test p_astro values using CBC catalog paper
    values for GW170817, for various mock-FARs, to test
    handling of this very loud event for MBTA, PyCBC
    and spiir.
    """
    # values based on G322759
    snr = 33.
    mass1 = 1.77
    mass2 = 1.07

    p_astros = json.loads(
        p_astro.compute_p_astro(snr, far, mass1, mass2,
                                pipeline, instruments))

    assert pytest.approx(p_astros['BNS'], abs=1e-1) == val
