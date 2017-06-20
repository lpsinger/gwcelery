# Standard library imports
import json
import os
from tempfile import NamedTemporaryFile

# Third-party imports
import astropy.io.fits
from celery import Celery, chain, group
from celery.utils.log import get_task_logger
from lalinference.scripts import bayestar_plot_allsky
from lalinference.scripts import bayestar_plot_volume
from ligo.gracedb.rest import GraceDb


# Celery application object
app = Celery('tasks', backend='rpc://', broker='pyamqp://')

# Use pickle serializer, because it supports byte values
app.conf.update(
    accept_content=['pickle'],
    event_serializer='pickle',
    result_serializer='pickle',
    task_serializer='pickle')

# Logging
log = get_task_logger(__name__)


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


@app.task
def download(filename, graceid, service):
    """Download a file from GraceDB."""
    return GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(ignore_result=True)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    if filecontents is None:
        return
    log.info('uploading to gracedb: %s %s', graceid, filename)
    GraceDb(service).writeLog(graceid, message, filename, filecontents, tags)


@app.task
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='wb') as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        fitsfile.write(filecontents)
        fitsfile.flush()
        bayestar_plot_allsky.main([
            fitsfile.name, '-o', pngfile.name, '--annotate',
            '--contour', '50', '90'])
        return pngfile.read()


def is_3d_fits_file(f):
    try:
        if astropy.io.fits.getval(f, 'TUNIT4', 1) == 'Mpc-2':
            return True
    except (KeyError, IndexError):
        pass
    return False


@app.task
def plot_volume(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='wb') as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        fitsfile.write(filecontents)
        fitsfile.flush()
        if not is_3d_fits_file(fitsfile.name):
            return None
        bayestar_plot_volume.main([
            fitsfile.name, '-o', pngfile.name, '--annotate'])
        return pngfile.read()
