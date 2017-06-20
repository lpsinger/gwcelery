import json
import os

from ..celery import app
from .gracedb import download, upload
from .skymaps import annotate_fits


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
