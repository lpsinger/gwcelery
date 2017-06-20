# Standard library imports
from __future__ import print_function
from contextlib import contextmanager
import io
import json
import os
from tempfile import NamedTemporaryFile as _NamedTemporaryFile

# Third-party imports
import astropy.io.fits
from celery import Celery, group
from celery.utils.log import get_task_logger
from ligo.gracedb.rest import GraceDb
import six


# Celery application object.
# Use pickle serializer, because it supports byte values.
app = Celery('tasks', backend='redis://', broker='redis://', config_source=dict(
    accept_content=['json', 'pickle'],
    event_serializer='json',
    result_serializer='pickle',
    task_serializer='pickle'
))

# Logging
log = get_task_logger(__name__)


@contextmanager
def NamedTemporaryFile(**kwargs):
    """Convenience wrapper for NamedTemporaryFile that writes some data to
    the file before handing it to the calling code."""
    # Make a copy so that we don't modify kwargs
    kwargs = dict(kwargs)

    content = kwargs.pop('content', None)
    if isinstance(content, six.binary_type):
        kwargs['mode'] = 'w+b'
    elif isinstance(content, six.text_type):
        kwargs['mode'] = 'w+'
    elif content is not None:
        raise TypeError('content is of unknown type')
    with _NamedTemporaryFile(**kwargs) as f:
        if content is not None:
            f.write(content)
            f.flush()
            f.seek(0)
        yield f


@app.task(ignore_result=True)
def dispatch(payload):
    """Parse an LVAlert message and dispatch it to other tasks."""
    # Parse JSON payload
    alert = json.loads(payload)

    # Determine GraceDB service URL
    try:
        self_link = alert['object']['links']['self']
    except KeyError:
        self_link = alert['object']['self']
    base, api, _ = self_link.partition('/api/')
    service = base + api

    # Determine GraceDB ID
    graceid = alert['uid']

    if alert['alert_type'] == 'update' and alert.get('file'):
        _, versioned_filename = os.path.split(alert['object']['file'])
        filename, _, _ = versioned_filename.rpartition(',')
        filebase, fitsext, _ = filename.rpartition('.fits')
        tags = alert['object']['tag_names']
        if fitsext:
            annotate_fits(versioned_filename, filebase, graceid, service, tags)
        elif filename == 'psd.xml.gz':
            (group(download.s('coinc.xml', graceid, service), download.s('psd.xml.gz', graceid, service)) | bayestar.s(graceid, service) | upload.s('bayestar.fits.gz', graceid, service, 'sky localization complete', 'sky_loc')).delay()


def annotate_fits(versioned_filename, filebase, graceid, service, tags):
    """Perform various annotations on a sky map."""
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
    (fits_header.s(versioned_filename, content) | upload.s(filebase + '.html', graceid, service, fits_header_message, tags)).delay()
    (plot_allsky.s(content) | upload.s(filebase + '.png', graceid, service, plot_allsky_message, tags)).delay()
    (is_3d_fits_file.s(content) | plot_volume.s() | upload.s(filebase + '.volume.png', graceid, service, plot_volume_message, tags)).delay()



@app.task(queue='openmp')
def bayestar(coinc_psd, graceid, service):
    from lalinference.io.events import ligolw
    from lalinference.io import fits
    from lalinference.bayestar.command import TemporaryDirectory
    from lalinference.bayestar.sky_map import localize, rasterize

    # Parse event
    coinc, psd = coinc_psd
    coinc = io.BytesIO(coinc)
    psd = io.BytesIO(psd)
    event, = ligolw.open(coinc, psd_file=psd, coinc_def=None).values()

    # Run BAYESTAR
    skymap = rasterize(localize(event))
    skymap.meta['objid'] = str(graceid)

    with TemporaryDirectory() as tmpdir:
        fitspath = os.path.join(tmpdir, 'bayestar.fits.gz')
        fits.write_sky_map(fitspath, skymap, nest=True)
        return open(fitspath, 'rb').read()


@app.task
def download(filename, graceid, service):
    """Download a file from GraceDB."""
    return GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(ignore_result=True)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    GraceDb(service).writeLog(graceid, message, filename, filecontents, tags)


@app.task
def fits_header(filename, filecontents):
    """Plot a Mollweide projection of a sky map."""
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


@app.task
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    from lalinference.scripts.bayestar_plot_allsky import main
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        main([fitsfile.name, '-o', pngfile.name, '--annotate',
              '--contour', '50', '90'])
        return pngfile.read()


@app.task(raises=ValueError)
def is_3d_fits_file(filecontents):
    try:
        with NamedTemporaryFile(content=filecontents) as fitsfile:
            if astropy.io.fits.getval(fitsfile.name, 'TUNIT4', 1) == 'Mpc-2':
                return filecontents
    except (KeyError, IndexError):
        raise ValueError('Not a 3D FITS file')


@app.task(queue='openmp')
def plot_volume(filecontents):
    """Plot a Mollweide projection of a sky map."""
    from lalinference.scripts.bayestar_plot_volume import main
    with NamedTemporaryFile(content=filecontents) as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        main([fitsfile.name, '-o', pngfile.name, '--annotate'])
        return pngfile.read()
