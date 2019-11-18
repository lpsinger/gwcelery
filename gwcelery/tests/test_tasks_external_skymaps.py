from unittest.mock import patch

import pkg_resources
import pytest

from . import resource_json
from .test_tasks_skymaps import toy_fits_filecontents  # noqa: F401
from .test_tasks_skymaps import toy_3d_fits_filecontents  # noqa: F401
from ..tasks import external_skymaps


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
def test_create_combined_skymap():
    """Test creating combined LVC and Fermi skymap"""
    # Run function under test
    external_skymaps.create_combined_skymap('S12345')


@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
def test_get_preferred_skymap():
    """Test getting the LVC skymap fits filename"""
    external_skymaps.get_preferred_skymap('S12345')


@patch('gwcelery.tasks.gracedb.get_event', mock_get_event)
@patch('gwcelery.tasks.gracedb.get_superevent',
       return_value={'em_events': ['E12345']})
def test_external_trigger(mock_get_superevent, mock_download):
    """Test getting related em event for superevent"""
    assert external_skymaps.external_trigger('S12345') == 'E12345'


@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
def test_external_trigger_heasarc(mock_download):
    """Test retrieving HEASARC fits file link from GCN"""
    heasarc_link = external_skymaps.external_trigger_heasarc('E12345')
    assert heasarc_link == true_heasarc_link


@patch('urllib.request.urlopen')
def test_get_external_skymap(mock_urlopen):
    """Assert that the correct call to astropy.get_file_contents is used"""
    external_skymaps.get_external_skymap(true_heasarc_link)

    mock_urlopen.assert_called_once()


def test_get_upload_external_skymap():
    """Test that an external sky map is grabbed and uploaded."""
    graceid = 'E12345'
    external_skymaps.get_upload_external_skymap(graceid)


@pytest.mark.parametrize('ra,dec,error,pix',
                         [[0, 90, 0, 0],
                          [270, -90, .01, -1]])
def test_create_swift_skymap(ra, dec, error, pix):
    """Test created single pixel sky maps for Swift localization."""
    skymap = external_skymaps.create_external_skymap(ra, dec, error)
    assert skymap[pix] == 1


def test_create_fermi_skymap():
    """Test created single pixel sky maps for Swift localization."""
    ra, dec, error = 0, 90, 10
    external_skymaps.create_external_skymap(ra, dec, error)


@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.skymaps.plot_allsky.run')
def test_create_upload_swift_skymap(mock_plot_allsky,
                                    mock_upload):
    """Test the creation and upload of sky maps for Swift localization."""
    event = {'graceid': 'E1234',
             'pipeline': 'Swift',
             'gpstime': 1259790538.77,
             'extra_attributes': {
                 'GRB': {
                     'trigger_id': 1234567,
                     'ra': 0,
                     'dec': 0,
                     'error_radius': 0}},
             'links': {
                 'self': 'https://gracedb.ligo.org/api/events/E356793'}}
    external_skymaps.create_upload_external_skymap(event)
    mock_upload.assert_called()
    mock_plot_allsky.assert_called_once()