import argparse
import gzip
from importlib import resources
import io
import os
from unittest.mock import patch

from astropy.table import Table
import numpy as np
import pytest

from ..tasks import skymaps
from . import data


def get_toy_fits_filecontents():
    bytesio = io.BytesIO()
    table = Table([[1, 2, 3], [4, 5, 6]], names=['foo', 'bar'],
                  dtype=[np.float64, np.float64])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line. <This should be escaped.>'
    table.meta['OBJECT'] = 'T12345'
    table.meta['LOGBCI'] = 3.5
    table.meta['ORDERING'] = 'NESTED'
    with gzip.GzipFile(fileobj=bytesio, mode='wb') as f:
        table.write(f, format='fits')
    return bytesio.getvalue()


@pytest.fixture
def toy_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    return get_toy_fits_filecontents()


def get_toy_3d_fits_filecontents():
    bytesio = io.BytesIO()
    table = Table(
        [np.arange(12, dtype=np.float64)] * 4,
        names=['PROB', 'DISTMU', 'DISTSIGMA', 'DISTNORM'])
    table.meta['comment'] = 'This is a comment.'
    table.meta['history'] = 'This is a history line. <This should be escaped.>'
    table.meta['OBJECT'] = 'T12345'
    table.meta['LOGBCI'] = 3.5
    table.meta['ORDERING'] = 'NESTED'
    with gzip.GzipFile(fileobj=bytesio, mode='wb') as f:
        table.write(f, format='fits')
    return bytesio.getvalue()


@pytest.fixture
def toy_3d_fits_filecontents():
    """Generate the binary contents of a toy FITS file."""
    return get_toy_3d_fits_filecontents()


def mock_download(filename, graceid):
    if filename == 'test.fits,0' and graceid == 'T12345':
        return get_toy_3d_fits_filecontents()
    else:
        raise RuntimeError('Asked for unexpected FITS file')


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('ligo.skymap.tool.ligo_skymap_plot.main')
@patch('ligo.skymap.tool.ligo_skymap_plot_volume.main')
def test_annotate_fits(mock_plot_volume, mock_plot, toy_3d_fits_filecontents):
    skymaps.annotate_fits(
        toy_3d_fits_filecontents, 'test.fits,0', 'T12345', ['tag1'])


def test_fits_header(toy_fits_filecontents):
    # Run function under test
    html = skymaps.fits_header(toy_fits_filecontents, 'test.fits')

    # Check output
    assert html == resources.read_text(data, 'fits_header_result.html')


@patch('ligo.skymap.tool.ligo_skymap_plot.main')
def test_plot_allsky(mock_plot):
    # Run function under test
    skymaps.plot_allsky('')

    # Check that the script would have been run once
    # with the correct arguments
    mock_plot.assert_called_once()
    cmdline, = mock_plot.call_args[0]
    assert cmdline[2].endswith('.png')


@patch('ligo.skymap.tool.ligo_skymap_plot.main')
def test_plot_allsky_swift(mock_plot):
    # Run function under test
    skymaps.plot_allsky('', ra=0, dec=0)

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


def test_skymap_from_samples(toy_3d_fits_filecontents):

    def mock_skymap_from_samples(args):
        parser = argparse.ArgumentParser()
        parser.add_argument('--outdir', '-o', default='.')
        parser.add_argument('--fitsoutname', default='skymap.fits')
        parser.add_argument('samples')
        parser.add_argument('--jobs', '-j', action='store_true')
        args = parser.parse_args(args)
        with open(os.path.join(args.outdir, args.fitsoutname), 'wb') as f:
            f.write(toy_3d_fits_filecontents)

    inbytes = resources.read_binary(data, 'samples.hdf5')

    with patch('ligo.skymap.tool.ligo_skymap_from_samples.main',
               mock_skymap_from_samples):
        outbytes = skymaps.skymap_from_samples(inbytes)

    assert skymaps.is_3d_fits_file(outbytes)


@patch('gwcelery.tasks.gracedb.download.run', mock_download)
@patch('gwcelery.tasks.gracedb.upload.run')
def test_handle_plot_coherence(mock_upload):
    alert = {
        "data": {
            "filename": "test.fits",
            "file_version": 0
        },
        "uid": "T12345",
        "alert_type": "log"
    }

    skymaps.handle_plot_coherence(alert)
    mock_upload.assert_called_once()
