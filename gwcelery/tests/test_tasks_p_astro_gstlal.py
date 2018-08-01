import json

import numpy as np
import pkg_resources
import pytest

from .. import app
from ..tasks import p_astro_gstlal


@pytest.fixture
def ranking_data_bytes():
    return pkg_resources.resource_string(
        __name__, 'data/ranking_data_G322589.xml.gz')


@pytest.fixture
def coinc_bytes():
    return pkg_resources.resource_string(
        __name__, 'data/coinc_G322589.xml')


@pytest.fixture(autouse=True, scope='module')
def mock_trigger_db():
    old = app.conf['p_astro_gstlal_trigger_db']
    app.conf['p_astro_gstlal_trigger_db'] = pkg_resources.resource_filename(
        __name__, 'data/p_astro_gstlal_trigger_db.sqlite')
    yield
    app.conf['p_astro_gstlal_trigger_db'] = old


def test_get_ln_f_over_b(ranking_data_bytes):
    """Test to check :meth:`_get_ln_f_over_b` returns values
    which are not inf or nan for high ln_likelihood_ratio"""
    ln_f_over_b = p_astro_gstlal._get_ln_f_over_b(
        ranking_data_bytes, [100., 200., 300.])
    assert np.all(np.isfinite(ln_f_over_b))


def test_get_event_ln_likelihood_ratio_svd_endtime_mass(coinc_bytes):
    likelihood, gamma1, end_time, mass = \
        p_astro_gstlal._get_event_ln_likelihood_ratio_svd_endtime_mass(
            coinc_bytes)
    assert likelihood == pytest.approx(21.65, abs=0.1)
    assert gamma1 == pytest.approx(90)
    assert end_time == pytest.approx(1174052512)
    assert mass == pytest.approx(3.78, abs=0.1)


def test_load_search_results(coinc_bytes):
    """Fake trigger database returns SVD bank number as 28"""
    likelihood, gamma1, end_time, mass = \
        p_astro_gstlal._get_event_ln_likelihood_ratio_svd_endtime_mass(
            coinc_bytes)
    background, zerolag, svd_banks = \
        p_astro_gstlal._load_search_results(end_time, mass, 6)
    assert np.all(svd_banks == 28)
    background, zerolag, svd_banks = \
        p_astro_gstlal._load_search_results(end_time, mass, 6)
    assert np.all(svd_banks == 28)


def test_compute_p_astro(coinc_bytes, ranking_data_bytes):
    """Test to call :meth:`compute_p_astro` on gracedb event G322589.
    m1 = 2.7, m2 = 1.0 solar mass for this event"""
    files = coinc_bytes, ranking_data_bytes
    p_astros = json.loads(p_astro_gstlal.compute_p_astro(files))

    assert p_astros['BNS'] == pytest.approx(1, abs=1e-3)
    assert p_astros['NSBH'] == pytest.approx(0, abs=1e-3)
    assert p_astros['BBH'] == pytest.approx(0, abs=1e-3)
    assert p_astros['Terr'] == pytest.approx(0, abs=1e-3)
