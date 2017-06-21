import io
import pkg_resources
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from astropy.io import fits
from astropy.table import Table
import pytest

from ..tasks import skymaps


@pytest.fixture
def toy_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table(data=[[1, 2, 3], [4, 5, 6]], names=['foo', 'bar'])
    table.write(bytesio, format='fits')
    return bytesio.getvalue()


@pytest.fixture
def toy_3d_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table(
        data=[[0] * 12] * 4, names=['PROB', 'DISTMU', 'DISTSIGMA', 'DISTNORM'])
    table.write(bytesio, format='fits')
    return bytesio.getvalue()


def test_annotate_fits():
    pass # TODO


def test_fits_header(toy_fits_filecontents):
    # Run function under test
    html = skymaps.fits_header('test.fits', toy_fits_filecontents)

    # Check output
    assert html == pkg_resources.resource_string(
        __name__, 'data/fits_header_result.html')


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
