"""Routing of LVAlert messages to other tasks."""
import json
import os

from ..celery import app
from .bayestar import bayestar
from .skymaps import annotate_fits
# from .voevent import send


@app.task(ignore_result=True, shared=False)
def dispatch(payload):
    """Parse an LVAlert message and dispatch it to other tasks."""
    # Parse JSON payload
    alert = json.loads(payload)

    # Determine GraceDB service URL
    try:
        try:
            self_link = alert['object']['links']['self']
        except KeyError:
            self_link = alert['object']['self']
    except KeyError:
        # Cannot deduce API link
        return
    base, api, _ = self_link.partition('/api/')
    service = base + api

    # Determine GraceDB ID
    graceid = alert['uid']

    if alert['alert_type'] == 'update' and 'voevent_type' in alert['object']:
        # FIXME: temporarily disable sending GCNs as per P. Brady request
        pass  # send.delay(alert['object']['text'])
    elif alert['alert_type'] == 'update' and alert.get('file'):
        _, versioned_filename = os.path.split(alert['object']['file'])
        filename, _, _ = versioned_filename.rpartition(',')
        filebase, fitsext, _ = filename.rpartition('.fits')
        tags = alert['object']['tag_names']
        if fitsext:
            annotate_fits(
                versioned_filename, filebase, graceid, service, tags).delay()
        elif filename == 'psd.xml.gz':
            bayestar(graceid, service).delay()
