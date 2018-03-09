import io

from astropy.io import fits
from astropy.table import Table
import numpy as np

from ..tasks import skymaps
from . import *


def resource_unicode(*args, **kwargs):
    with open(pkg_resources.resource_filename(*args, **kwargs), 'r') as f:
        return f.read()


@pytest.fixture
def toy_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table([[1, 2, 3], [4, 5, 6]], names=['foo', 'bar'])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line.'
    table.meta['ORDERING'] = 'NESTED'
    table.write(bytesio, format='fits')
    return bytesio.getvalue()


@pytest.fixture
def toy_3d_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table(
        [np.arange(12)] * 4, names=['PROB', 'DISTMU', 'DISTSIGMA', 'DISTNORM'])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line.'
    table.meta['ORDERING'] = 'NESTED'
    table.write(bytesio, format='fits')
    return bytesio.getvalue()


def mock_download(filename, graceid, service):
    if (
            filename == 'test.fits,0' and graceid == 'T12345' and
            service == 'https://gracedb.invalid/api/'):
        return toy_3d_fits_filecontents()
    else:
        raise RuntimeError('Asked for unexpected FITS file')


@patch('gwcelery.tasks.skymaps.download', mock_download)
@patch('gwcelery.tasks.skymaps.check_call')
@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_annotate_fits(mock_gracedb, check_call):
    skymaps.annotate_fits('test.fits,0', 'test', 'T12345',
                          'https://gracedb.invalid/api/',
                          ['tag1']).apply().get()


def test_fits_header(toy_fits_filecontents):
    # Run function under test
    html = skymaps.fits_header('test.fits', toy_fits_filecontents)

    # Check output
    assert html == resource_unicode(__name__, 'data/fits_header_result.html')


@patch('gwcelery.tasks.skymaps.check_call')
def test_plot_allsky(mock_check_call):
    # Run function under test
    skymaps.plot_allsky('')

    # Check that the script would have been run once
    # with the correct arguments
    mock_check_call.assert_called_once()
    cmdline, = mock_check_call.call_args[0]
    assert cmdline[0] == 'bayestar_plot_allsky'
    assert cmdline[3].endswith('.png')


def test_is_3d_fits_file(toy_fits_filecontents, toy_3d_fits_filecontents):
    # This is not a 3D FITS file.
    with pytest.raises(ValueError):
        skymaps.is_3d_fits_file(toy_fits_filecontents)
    # This is a 3D FITS file.
    skymaps.is_3d_fits_file(toy_3d_fits_filecontents)


@patch('gwcelery.tasks.skymaps.check_call')
def test_plot_volume(mock_check_call):
    # Run function under test
    skymaps.plot_volume('')

    # Check that the script would have been run once
    # with the correct arguments
    mock_check_call.assert_called_once()
    cmdline, = mock_check_call.call_args[0]
    assert cmdline[0] == 'bayestar_plot_volume'
    assert cmdline[-2].endswith('.png')
