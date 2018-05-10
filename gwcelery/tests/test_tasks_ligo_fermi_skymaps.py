from unittest.mock import patch

from ligo.gracedb import rest
import pkg_resources

from . import resource_json
from . import test_tasks_skymaps
from ..tasks import ligo_fermi_skymaps


def mock_get_superevent(graceid):
    return resource_json(__name__, 'data/mock_superevent_object.json')


def mock_get_log(graceid):
    if graceid == 'S12345':
        return resource_json(__name__, 'data/gracedb_setrigger_log.json')
    elif graceid == 'E12345':
        return resource_json(__name__, 'data/gracedb_externaltrigger_log.json')
    else:
        raise ValueError


def mock_download(filename, graceid):
    """Mocks GraceDb download functionality"""
    if graceid == 'S12345' and filename == 'bayestar.fits.gz':
        return test_tasks_skymaps.toy_3d_fits_filecontents()
    elif (graceid == 'E12345' and
          filename == ('nasa.gsfc.gcn_Fermi%23GBM_Gnd_Pos_2017-08-17'
                       + 'T12%3A41%3A06.47_524666471_57-431.xml')):
        return pkg_resources.resource_string(
                   __name__, 'data/externaltrigger_original_data.xml'
               )
    else:
        raise ValueError


def mock_get_file_contents(heasarc_link):
    """Mocks astropy get_file_contents functionality"""
    assert heasarc_link == (
        'http://heasarc.gsfc.nasa.gov/FTP/fermi/data/gbm/'
        + 'triggers/2017/bn170817529/current/'
    )
    return test_tasks_skymaps.toy_fits_filecontents()


@patch('gwcelery.tasks.gracedb.get_superevent', mock_get_superevent)
@patch('gwcelery.tasks.gracedb.get_log', mock_get_log)
@patch('gwcelery.tasks.gracedb.download', mock_download)
@patch('astropy.utils.data.get_file_contents', mock_get_file_contents)
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_create_combined_skymap(graceid):
    """Test creating combined LVC and Fermi skymap"""
    # Run function under test
    ligo_fermi_skymaps.create_combined_skymap('S12345')
