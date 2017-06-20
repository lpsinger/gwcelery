# Standard library imports
import json
import os
from tempfile import NamedTemporaryFile

# Third-party imports
from celery import Celery
from celery.utils.log import get_task_logger
from lalinference.scripts.bayestar_plot_allsky import main
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
    base, api, _ = alert['object']['self'].partition('/api/')
    service = base + api

    # Determine GraceDB ID
    graceid = alert['uid']

    if alert['alert_type'] == 'update':
        _, versioned_filename = os.path.split(alert['object']['file'])
        filename, _, _ = versioned_filename.rpartition(',')
        filebase, fitsext, _ = filename.rpartition('.fits')
        tags = alert['object']['tags']
        if fitsext:
            annotate_fits(versioned_filename, filebase, graceid, service, tags)


def annotate_fits(versioned_filename, filebase, graceid, service, tags):
    """Perform various annotations on a sky map."""
    plot_allsky_message = (
        'Mollweide projection of <a href="/apiweb/events/{graceid}/files/'
        '{versioned_filename}>{versioned_filename}</a>').format(
            graceid=graceid, versioned_filename=versioned_filename)
    (download.s(versioned_filename, graceid, service)
     | plot_allsky.s()
     | upload.s(filebase + '.png', graceid, service, plot_allsky_message, tags)
    ).delay()


@app.task
def download(filename, graceid, service):
    """Download a file from GraceDB."""
    return GraceDb(service).files(graceid, filename, raw=True).read()


@app.task(ignore_result=True)
def upload(filecontents, filename, graceid, service, message, tags):
    """Upload a file to GraceDB."""
    GraceDb(service).writeLog(graceid, message, filename, filecontents, tags)


@app.task
def plot_allsky(filecontents):
    """Plot a Mollweide projection of a sky map."""
    with NamedTemporaryFile(mode='wb') as fitsfile, \
         NamedTemporaryFile(mode='rb', suffix='.png') as pngfile:
        fitsfile.write(filecontents)
        fitsfile.flush()
        main([fitsfile.name, '-o', pngfile.name,
              '--annotate', '--contour', '50', '90'])
        return pngfile.read()
