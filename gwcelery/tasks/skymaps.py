"""Annotations for sky maps."""
import os
import tempfile

from astropy.io import fits
from astropy import table
from celery import group
from ligo.skymap.tool import ligo_skymap_flatten
from ligo.skymap.tool import ligo_skymap_plot
from ligo.skymap.tool import ligo_skymap_plot_volume
from matplotlib import pyplot as plt

from . import gracedb
from ..import app
from ..jinja import env
from ..util.tempfile import NamedTemporaryFile


def annotate_fits(versioned_filename, graceid, tags):
    """Perform annotations on a sky map.

    This function downloads a FITS file and then generates and uploads all
    derived images as well as an HTML dump of the FITS header.
    """
    filebase = versioned_filename.partition('.fits')[0]
    header_msg = (
        'FITS headers for <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    allsky_msg = (
        'Mollweide projection of <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    volume_msg = (
        'Volume rendering of <a href="/api/superevents/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)

    return group(
        fits_header.s(versioned_filename) |
        gracedb.upload.s(
            filebase + '.html', graceid, header_msg, tags),

        plot_allsky.s() |
        gracedb.upload.s(
            filebase + '.png', graceid, allsky_msg, tags),

        annotate_fits_volume.s(
            filebase + '.volume.png', graceid, volume_msg, tags)
    )


def is_3d_fits_file(filecontents):
    """Determine if a FITS file has distance information."""
    with NamedTemporaryFile(content=filecontents) as fitsfile:
        return 'DISTNORM' in table.Table.read(fitsfile.name).colnames


@app.task(ignore_result=True, shared=False)
def annotate_fits_volume(filecontents, *args):
    """Perform annotations that are specific to 3D sky maps."""
    if is_3d_fits_file(filecontents):
        (
            plot_volume.s(filecontents)
            |
            gracedb.upload.s(*args)
        ).apply_async()


@app.task(shared=False)
def fits_header(filecontents, filename):
    """Dump FITS header to HTML."""
    template = env.get_template('fits_header.jinja2')
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
            fits.open(fitsfile.name) as hdus:
        return template.render(filename=filename, hdus=hdus)


@app.task(shared=False)
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map using the command-line tool
    :doc:`ligo-skymap-plot <ligo/skymap/tool/ligo_skymap_plot>`."""
    # Note: plt.style.context added as workaround for
    # https://github.com/astropy/astropy/issues/8004.
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile, \
            plt.style.context({'text.usetex': False}, after_reset=True):
        ligo_skymap_plot.main([fitsfile.name, '-o', pngfile.name,
                               '--annotate', '--contour', '50', '90'])
        return pngfile.read()


@app.task(queue='openmp', shared=False)
def plot_volume(filecontents):
    """Plot a 3D volume rendering of a sky map using the command-line tool
    :doc:`ligo-skymap-plot-volume <ligo/skymap/tool/ligo_skymap_plot_volume>`.
    """
    # Note: plt.style.context added as workaround for
    # https://github.com/astropy/astropy/issues/8004.
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile, \
            plt.style.context({'text.usetex': False}, after_reset=True):
        ligo_skymap_plot_volume.main([fitsfile.name, '-o',
                                      pngfile.name, '--annotate'])
        return pngfile.read()


@app.task(shared=False)
def flatten(filecontents, filename):
    """Convert a HEALPix FITS file from multi-resolution UNIQ indexing to the
    more common IMPLICIT indexing using the command-line tool
    :doc:`ligo-skymap-flatten <ligo/skymap/tool/ligo_skymap_flatten>`."""
    with NamedTemporaryFile(content=filecontents) as infile, \
            tempfile.TemporaryDirectory() as tmpdir:
        outfilename = os.path.join(tmpdir, filename)
        ligo_skymap_flatten.main([infile.name, outfilename])
        return open(outfilename, 'rb').read()
