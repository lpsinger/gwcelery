import io
import pkg_resources
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from astropy.io import fits
from astropy.table import Table

from ..tasks import skymaps


def test_annotate_fits():
    pass # TODO


def test_fits_header(tmpdir):
    # Construct example FITS file
    filename = 'test.fits'
    bytesio = io.BytesIO()
    Table(data=[[1, 2, 3], [4, 5, 6]], names=['foo', 'bar']).write(
        bytesio, format='fits')
    filecontents = bytesio.getvalue()

    # Run function under test
    html = skymaps.fits_header(filename, filecontents)

    # Check output
    assert html == pkg_resources.resource_string(
        __name__, 'data/fits_header_result.html')


def test_plot_allsky():
    pass # TODO


def test_is_3d_fits_file():
    pass # TODO


def test_plot_volume():
    pass # TODO
