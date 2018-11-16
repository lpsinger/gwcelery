import gzip
import io
from unittest.mock import patch

from astropy.table import Table
from ligo.gracedb import rest
import numpy as np
import pkg_resources
import pytest

from ..tasks import skymaps


def resource_unicode(*args, **kwargs):
    with open(pkg_resources.resource_filename(*args, **kwargs), 'r') as f:
        return f.read()


@pytest.fixture
def toy_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table([[1, 2, 3], [4, 5, 6]], names=['foo', 'bar'],
                  dtype=[np.float64, np.float64])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line. <This should be escaped.>'
    table.meta['ORDERING'] = 'NESTED'
    with gzip.GzipFile(fileobj=bytesio, mode='wb') as f:
        table.write(f, format='fits')
    return bytesio.getvalue()


@pytest.fixture
def toy_3d_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    bytesio = io.BytesIO()
    table = Table(
        [np.arange(12, dtype=np.float64)] * 4,
        names=['PROB', 'DISTMU', 'DISTSIGMA', 'DISTNORM'])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line. <This should be escaped.>'
    table.meta['ORDERING'] = 'NESTED'
    with gzip.GzipFile(fileobj=bytesio, mode='wb') as f:
        table.write(f, format='fits')
    return bytesio.getvalue()


def mock_download(filename, graceid):
    if filename == 'test.fits,0' and graceid == 'T12345':
        return toy_3d_fits_filecontents()
    else:
        raise RuntimeError('Asked for unexpected FITS file')


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
@patch('ligo.skymap.tool.ligo_skymap_plot.main')
@patch('ligo.skymap.tool.ligo_skymap_plot_volume.main')
def test_annotate_fits(mock_plot_volume, mock_plot, mock_gracedb,
                       toy_3d_fits_filecontents):
    skymaps.annotate_fits('test.fits,0', 'T12345', ['tag1']).delay(
        toy_3d_fits_filecontents).get()


def test_fits_header(toy_fits_filecontents):
    # Run function under test
    html = skymaps.fits_header(toy_fits_filecontents, 'test.fits')

    # Check output
    assert html == resource_unicode(__name__, 'data/fits_header_result.html')


@patch('ligo.skymap.tool.ligo_skymap_plot.main')
def test_plot_allsky(mock_plot):
    # Run function under test
    skymaps.plot_allsky('')

    # Check that the script would have been run once
    # with the correct arguments
    mock_plot.assert_called_once()
    cmdline, = mock_plot.call_args[0]
    assert cmdline[2].endswith('.png')


def test_is_3d_fits_file(toy_fits_filecontents, toy_3d_fits_filecontents):
    # This is not a 3D FITS file.
    assert not skymaps.is_3d_fits_file(toy_fits_filecontents)
    # This is a 3D FITS file.
    assert skymaps.is_3d_fits_file(toy_3d_fits_filecontents)


@patch('ligo.skymap.tool.ligo_skymap_plot_volume.main')
def test_plot_volume(mock_plot_volume):
    # Run function under test
    skymaps.plot_volume('')

    # Check that the script would have been run once
    # with the correct arguments
    mock_plot_volume.assert_called_once()
    cmdline, = mock_plot_volume.call_args[0]
    assert cmdline[-2].endswith('.png')
