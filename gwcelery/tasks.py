# Standard library imports
from tempfile import NamedTemporaryFile

# Third-party imports
from celery import Celery, group
from celery.utils.log import get_task_logger


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


@app.task(ignore_result=True)
def dispatch(payload):
    """Parse an LVAlert message and dispatch it to other tasks."""
    import json
    import os

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
    plot_allsky_message = (
        'Mollweide projection of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    plot_volume_message = (
        'Volume rendering of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}">{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    content = download(versioned_filename, graceid, service)
    (plot_allsky.s(content) |  upload.s(filebase + '.png', graceid, service, plot_allsky_message, tags)).delay()
    (plot_volume.s(content) |  upload.s(filebase + '.volume.png', graceid, service, plot_volume_message, tags)).delay()



@app.task(queue='openmp')
def bayestar(coinc_psd, graceid, service):
    import os
    from io import BytesIO
    from lalinference.io.events import ligolw
    from lalinference.io import fits
    from lalinference.bayestar.command import TemporaryDirectory
    from lalinference.bayestar.sky_map import localize, rasterize

    # Parse event
    coinc, psd = coinc_psd
    coinc = BytesIO(coinc)
    psd = BytesIO(psd)
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
    from ligo.gracedb.rest import GraceDb
    return GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(ignore_result=True)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    from ligo.gracedb.rest import GraceDb
    if filecontents is None:
        return
    log.info('uploading to gracedb: %s %s', graceid, filename)
    GraceDb(service).writeLog(graceid, message, filename, filecontents, tags)


@app.task
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    from lalinference.scripts.bayestar_plot_allsky import main
    with NamedTemporaryFile(mode='wb') as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        fitsfile.write(filecontents)
        fitsfile.flush()
        main([fitsfile.name, '-o', pngfile.name, '--annotate',
              '--contour', '50', '90'])
        return pngfile.read()


def is_3d_fits_file(f):
    from astropy.io.fits import getval
    try:
        if getval(f, 'TUNIT4', 1) == 'Mpc-2':
            return True
    except (KeyError, IndexError):
        pass
    return False


@app.task(queue='openmp')
def plot_volume(filecontents):
    """Plot a Mollweide projection of a sky map."""
    from lalinference.scripts.bayestar_plot_volume import main
    with NamedTemporaryFile(mode='wb') as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        fitsfile.write(filecontents)
        fitsfile.flush()
        if not is_3d_fits_file(fitsfile.name):
            return None
        main([fitsfile.name, '-o', pngfile.name, '--annotate'])
        return pngfile.read()
