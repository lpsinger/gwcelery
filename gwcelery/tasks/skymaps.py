"""Annotations for sky maps."""
from __future__ import print_function
from subprocess import check_call

import astropy.io.fits
from celery import group
import six

from .gracedb import download, upload
from ..celery import app
from ..util.tempfile import NamedTemporaryFile


def annotate_fits(versioned_filename, filebase, graceid, service, tags):
    """Perform annotations on a sky map.

    This function downloads a FITS file and then generates and uploads all
    derived images as well as an HTML dump of the FITS header.
    """
    fits_header_message = (
        'FITS headers for <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    plot_allsky_message = (
        'Mollweide projection of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    plot_volume_message = (
        'Volume rendering of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    content = download(versioned_filename, graceid, service)
    return group(
        fits_header.s(versioned_filename, content) | upload.s(filebase + '.html', graceid, service, fits_header_message, tags),
        plot_allsky.s(content) | upload.s(filebase + '.png', graceid, service, plot_allsky_message, tags),
        is_3d_fits_file.s(content) | plot_volume.s() | upload.s(filebase + '.volume.png', graceid, service, plot_volume_message, tags)
    )


@app.task(shared=False)
def fits_header(filename, filecontents):
    """Dump FITS header to HTML."""
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         astropy.io.fits.open(fitsfile.name) as hdus:
        out = six.StringIO()
        print('<!DOCTYPE html>', file=out)
        print('<html lang="en">', file=out)
        print('<head>', file=out)
        print('<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous">', file=out)
        print('<title>FITS headers for ', filename, '</title>', sep='', file=out)
        print('</head>', file=out)
        print('<body>', file=out)
        print('<div class=container>', file=out)
        print('<h1>FITS headers for ', filename, '</h1>', sep='', file=out)
        print('<table class="table table-condensed table-striped">', file=out)
        print('<thead>', file=out)
        print('<tr>', file=out)
        print('<th>Keyword</th>', file=out)
        print('<th>Value</th>', file=out)
        print('<th>Comment</th>', file=out)
        print('</tr>', file=out)
        print('</thead>', file=out)
        print('<tbody>', file=out)
        for ihdu, hdu in enumerate(hdus):
            print('<tr class="info"><td colspan=3><strong>HDU #', ihdu, ' in ',
                  filename, '</strong></td></tr>', sep='', file=out)
            for card in hdu.header.cards:
                print('<tr>', file=out)
                print('<td style="font-family: monospace">', card.keyword, '</td>', sep='', file=out)
                if card.keyword in ('COMMENT', 'HISTORY'):
                    print('<td colspan=2>', card.value, '</td>', sep='', file=out)
                else:
                    print('<td style="font-family: monospace">', card.value, '</td>', sep='', file=out)
                    print('<td>', card.comment, '</td>', sep='', file=out)
                print('</tr>', file=out)
        print('</tbody>', file=out)
        print('</table>', file=out)
        print('</div>', file=out)
        print('</body>', file=out)
        print('</html>', file=out)
    return out.getvalue()


@app.task(shared=False)
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        check_call(['bayestar_plot_allsky', fitsfile.name, '-o', pngfile.name,
                    '--annotate', '--contour', '50', '90'])
        return pngfile.read()


@app.task(shared=False, throws=ValueError)
def is_3d_fits_file(filecontents):
    """Determine if a FITS file has distance information. If it does, then
    the file contents are returned. If it does not, then a :obj:`ValueError` is
    raised."""
    try:
        with NamedTemporaryFile(content=filecontents) as fitsfile:
            if astropy.io.fits.getval(fitsfile.name, 'TTYPE4', 1) == 'DISTNORM':
                return filecontents
    except (KeyError, IndexError):
        raise ValueError('Not a 3D FITS file')


@app.task(queue='openmp', shared=False)
def plot_volume(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        check_call(['bayestar_plot_volume', fitsfile.name, '-o', pngfile.name,
                    '--annotate'])
        return pngfile.read()
