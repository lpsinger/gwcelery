import json
from unittest.mock import patch

import pkg_resources
import pytest

from .. import app
from ..tasks import p_astro_gstlal


@pytest.fixture
def mock_url(monkeypatch):
    def _urlfunc(url):
        filename_m = "data/H1L1V1-mean_counts-1126051217-61603201.json"
        filename_w = "data/H1L1V1-weights-bins_686-1126051217-61603201.json"
        if url == app.conf['p_astro_url']:
            return pkg_resources.resource_stream(__name__, filename_m)
        elif url == app.conf['p_astro_weights_url']:
            return pkg_resources.resource_stream(__name__, filename_w)

    monkeypatch.setattr('urllib.request.urlopen', _urlfunc)


@pytest.fixture
def ranking_data_bytes():
    return pkg_resources.resource_string(
        __name__, 'data/ranking_data_G322589.xml.gz')


@pytest.fixture
def coinc_bytes_1():
    return pkg_resources.resource_string(
        __name__, 'data/coinc_G322589.xml')


@pytest.fixture
def coinc_bytes_2():
    return pkg_resources.resource_string(
        __name__, 'data/coinc_G5351.xml')


@pytest.fixture
def coinc_bytes_3():
    return pkg_resources.resource_string(
        __name__, 'data/coinc.xml')


def test_compute_p_astro_1(coinc_bytes_1, ranking_data_bytes, mock_url):
    """Test to call `compute_p_astro` on gracedb event G322589.
    m1 = 2.7, m2 = 1.0 solar mass for this event"""
    files = coinc_bytes_1, ranking_data_bytes

    p_astros = json.loads(p_astro_gstlal.compute_p_astro(files))

    assert p_astros['BNS'] == pytest.approx(1, abs=1e-2)
    assert p_astros['NSBH'] == pytest.approx(0, abs=1e-2)
    assert p_astros['BBH'] == pytest.approx(0, abs=1e-2)
    assert p_astros['MassGap'] == pytest.approx(0, abs=1e-2)
    assert p_astros['Terrestrial'] == pytest.approx(0, abs=1e-2)


def test_compute_p_astro_2(coinc_bytes_2, ranking_data_bytes, mock_url):
    """Test to call `compute_p_astro` on gracedb event G5351.
    m1 = 1.1, m2 = 1.0 solar mass for this event. FAR = 1.9e-6, P_terr
    has a moderate value."""
    files = coinc_bytes_2, ranking_data_bytes

    p_astros = json.loads(p_astro_gstlal.compute_p_astro(files))

    assert p_astros['Terrestrial'] > 0.25


def test_failing_compute_p_astro(coinc_bytes_3, ranking_data_bytes, mock_url):
    """Test the case when p_astro computation fails"""
    files = coinc_bytes_3, ranking_data_bytes
    with patch('gwcelery.tasks.p_astro_other.compute_p_astro') as p:
        p_astro_gstlal.compute_p_astro.s(files).delay()
        p.assert_called_once()


def test_handling_urlerror(coinc_bytes_3, ranking_data_bytes):
    """Test case when the request to fetch mean values results in
    a URLError if file is not found. p_astro_other should be called.
    """
    files = coinc_bytes_3, ranking_data_bytes
    with patch('gwcelery.tasks.p_astro_other.compute_p_astro') as p:
        p_astro_gstlal.compute_p_astro.s(files).delay()
        p.assert_called_once()
