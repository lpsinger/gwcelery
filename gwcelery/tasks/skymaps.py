"""Annotations for sky maps."""
from astropy.io import fits
from celery import group
from ligo.skymap.tool import ligo_skymap_plot
from ligo.skymap.tool import ligo_skymap_plot_volume

from . import gracedb
from ..celery import app
from ..jinja import env
from ..util.tempfile import NamedTemporaryFile


def annotate_fits(versioned_filename, filebase, graceid, tags):
    """Perform annotations on a sky map.

    This function downloads a FITS file and then generates and uploads all
    derived images as well as an HTML dump of the FITS header.
    """
    header_msg = (
        'FITS headers for <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    allsky_msg = (
        'Mollweide projection of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    volume_msg = (
        'Volume rendering of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)

    return gracedb.download.s(versioned_filename, graceid) | group(
        fits_header.s(versioned_filename) |
        gracedb.upload.s(
            filebase + '.html', graceid, header_msg, tags),

        plot_allsky.s() |
        gracedb.upload.s(
            filebase + '.png', graceid, allsky_msg, tags),

        is_3d_fits_file.s() |
        plot_volume.s() |
        gracedb.upload.s(
            filebase + '.volume.png', graceid, volume_msg, tags)
    )


@app.task(shared=False)
def fits_header(filecontents, filename):
    """Dump FITS header to HTML."""
    template = env.get_template('fits_header.html')
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
            fits.open(fitsfile.name) as hdus:
        return template.render(filename=filename, hdus=hdus)


@app.task(shared=False)
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile:
        ligo_skymap_plot.main([fitsfile.name, '-o', pngfile.name,
                               '--annotate', '--contour', '50', '90'])
        return pngfile.read()


@app.task(shared=False, throws=(ValueError,))
def is_3d_fits_file(filecontents):
    """Determine if a FITS file has distance information. If it does, then
    the file contents are returned. If it does not, then a :obj:`ValueError` is
    raised."""
    try:
        with NamedTemporaryFile(content=filecontents) as fitsfile:
            if fits.getval(fitsfile.name, 'TTYPE4', 1) == 'DISTNORM':
                return filecontents
    except (KeyError, IndexError):
        raise ValueError('Not a 3D FITS file')


@app.task(queue='openmp', shared=False)
def plot_volume(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile, \
            NamedTemporaryFile(content=filecontents) as fitsfile:
        ligo_skymap_plot_volume.main([fitsfile.name, '-o',
                                      pngfile.name, '--annotate'])
        return pngfile.read()
