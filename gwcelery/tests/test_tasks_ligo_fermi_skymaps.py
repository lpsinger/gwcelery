from unittest.mock import patch

from ligo.gracedb import rest
import pkg_resources
import pytest

from . import resource_json
from .test_tasks_skymaps import toy_fits_filecontents  # noqa: F401
from .test_tasks_skymaps import toy_3d_fits_filecontents  # noqa: F401
from ..tasks import ligo_fermi_skymaps


true_heasarc_link = ('http://heasarc.gsfc.nasa.gov/FTP/fermi/data/gbm/'
                     + 'triggers/2017/bn170817529/current/')
true_skymap_link = true_heasarc_link + 'glg_healpix_all_bn170817529_v00.fit'


def mock_get_event(exttrig):
    return {'search': 'GRB'}


def mock_get_superevent(graceid):
    return resource_json(__name__, 'data/mock_superevent_object.json')


def mock_get_log(graceid):
    if graceid == 'S12345':
        return resource_json(__name__, 'data/gracedb_setrigger_log.json')
    elif graceid == 'E12345':
        return resource_json(__name__, 'data/gracedb_externaltrigger_log.json')
    else:
        raise ValueError


@pytest.fixture  # noqa: F811
def mock_download(monkeypatch, toy_3d_fits_filecontents):  # noqa: F811

    def download(filename, graceid):
        """Mocks GraceDB download functionality"""
        if graceid == 'S12345' and filename == 'bayestar.fits.gz':
            return toy_3d_fits_filecontents
        elif (graceid == 'E12345' and
              filename == ('nasa.gsfc.gcn_Fermi%23GBM_Gnd_Pos_2017-08-17'
                           + 'T12%3A41%3A06.47_524666471_57-431.xml')):
            return pkg_resources.resource_string(
                       __name__, 'data/externaltrigger_original_data.xml'
                   )
        else:
            raise ValueError

    monkeypatch.setattr('gwcelery.tasks.gracedb.download.run', download)


def mock_get_file_contents(monkeypatch, toy_fits_filecontents):  # noqa: F811
    """Mocks astropy get_file_contents functionality"""

    def get_file_contents(heasarc_link):
        assert heasarc_link == true_heasarc_link
        return toy_fits_filecontents

    monkeypatch.setattr(
        'astropy.utils.data.get_file_contents', get_file_contents)


@patch('gwcelery.tasks.gracedb.get_superevent', mock_get_superevent)
@patch('gwcelery.tasks.gracedb.get_event', mock_get_event)
@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
@patch('astropy.utils.data.get_file_contents', mock_get_file_contents)
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_create_combined_skymap(graceid):
    """Test creating combined LVC and Fermi skymap"""
    # Run function under test
    ligo_fermi_skymaps.create_combined_skymap('S12345')


@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
def test_get_preferred_skymap():
    """Test getting the LVC skymap fits filename"""
    ligo_fermi_skymaps.get_preferred_skymap('S12345')


@patch('gwcelery.tasks.gracedb.get_event', mock_get_event)
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'em_events': ['E12345']})
def test_external_trigger(mock_get_superevent, mock_download):
    """Test getting related em event for superevent"""
    assert ligo_fermi_skymaps.external_trigger('S12345') == 'E12345'


@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
def test_external_trigger_heasarc(mock_download):
    """Test retrieving HEASARC fits file link from GCN"""
    heasarc_link = ligo_fermi_skymaps.external_trigger_heasarc('E12345')
    assert heasarc_link == true_heasarc_link


@patch('astropy.utils.data.get_file_contents')
def test_get_external_skymap(mock_astropy_get_file_contents):
    """Assert that the correct call to astropy.get_file_contents is used"""
    ligo_fermi_skymaps.get_external_skymap(true_heasarc_link)

    mock_astropy_get_file_contents.assert_called_once_with(
        (true_skymap_link), encoding='binary', cache=False)
