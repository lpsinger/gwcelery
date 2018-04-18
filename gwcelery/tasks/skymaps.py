"""Annotations for sky maps."""
from __future__ import print_function
import subprocess

from astropy.io import fits
from celery import group
import six

from . import gracedb
from ..celery import app
from ..util.tempfile import NamedTemporaryFile


def annotate_fits(versioned_filename, filebase, graceid, service, tags):
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

    return gracedb.download.s(versioned_filename, graceid, service) | group(
        fits_header.s(versioned_filename) |
        gracedb.upload.s(
            filebase + '.html', graceid, service, header_msg, tags),

        plot_allsky.s() |
        gracedb.upload.s(
            filebase + '.png', graceid, service, allsky_msg, tags),

        is_3d_fits_file.s() |
        plot_volume.s() |
        gracedb.upload.s(
            filebase + '.volume.png', graceid, service, volume_msg, tags)
    )


@app.task(shared=False)
def fits_header(filecontents, filename):
    """Dump FITS header to HTML."""
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         fits.open(fitsfile.name) as hdus:
        out = six.StringIO()
        print('<!doctype html>', file=out)
        print('<meta charset="utf-8">', file=out)
        print('<meta name="viewport" content="width=device-width, '
              'initial-scale=1, shrink-to-fit=no">', file=out)
        print('<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/'
              'bootstrap/4.0.0/css/bootstrap.min.css" integrity="sha384-'
              'Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" '
              'crossorigin="anonymous">', file=out)
        print('<title>FITS headers for ', filename, '</title>', sep='', file=out)
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
                print('<td style="font-family: monospace">', card.keyword, '</td>',
                      sep='', file=out)
                if card.keyword in ('COMMENT', 'HISTORY'):
                    print('<td colspan=2>', card.value, '</td>', sep='', file=out)
                else:
                    print('<td style="font-family: monospace">', card.value,
                          '</td>', sep='', file=out)
                    print('<td>', card.comment, '</td>', sep='', file=out)
                print('</tr>', file=out)
        print('</tbody>', file=out)
        print('</table>', file=out)
        print('</div>', file=out)
    return out.getvalue()


@app.task(shared=False)
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        with NamedTemporaryFile(content=filecontents) as fitsfile:
            subprocess.check_call(['bayestar_plot_allsky', fitsfile.name, '-o',
                                   pngfile.name, '--annotate',
                                   '--contour', '50', '90'])
        return pngfile.read()


@app.task(shared=False, throws=ValueError)
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
    with NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        with NamedTemporaryFile(content=filecontents) as fitsfile:
            subprocess.check_call(['bayestar_plot_volume', fitsfile.name, '-o',
                                   pngfile.name, '--annotate'])
        return pngfile.read()
