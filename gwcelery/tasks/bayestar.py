"""Rapid sky localization with BAYESTAR."""
import io
import logging
import os
import tempfile
import urllib.parse

from celery.exceptions import Ignore
from ligo.gracedb.logging import GraceDbLogHandler
from ligo.skymap import bayestar as _bayestar
from ligo.skymap.io import events
from ligo.skymap.io import fits

from ..celery import app
from . import gracedb

log = logging.getLogger('BAYESTAR')


@app.task(queue='openmp', shared=False)
def localize(coinc_psd, graceid, filename='bayestar.fits.gz',
             disabled_detectors=None):
    """Do the heavy lifting of generating a rapid localization using BAYESTAR.

    This function runs the computationally-intensive part of BAYESTAR.
    The `coinc.xml` and `psd.xml.gz` files should already have been downloaded
    by :func:`bayestar`.

    This task should execute in a special queue for computationally intensive
    OpenMP parallel tasks.
    """
    handler = GraceDbLogHandler(gracedb.client, graceid)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)

    # Determine the base URL for event pages.
    scheme, netloc, *_ = urllib.parse.urlparse(gracedb.client.service_url)
    base_url = urllib.parse.urlunparse((scheme, netloc, 'events', '', '', ''))

    try:
        # A little bit of Cylon humor
        log.info('by your command...')

        # Parse event
        coinc, psd = coinc_psd
        coinc = io.BytesIO(coinc)
        psd = io.BytesIO(psd)
        event_source = events.ligolw.open(coinc, psd_file=psd, coinc_def=None)
        if disabled_detectors:
            event_source = events.detector_disabled.open(
                event_source, disabled_detectors)
        event, = event_source.values()

        # Run BAYESTAR
        log.info("starting sky localization")
        skymap = _bayestar.rasterize(_bayestar.localize(event))
        skymap.meta['objid'] = str(graceid)
        skymap.meta['url'] = '{}/{}'.format(base_url, graceid)
        log.info("sky localization complete")

        with tempfile.TemporaryDirectory() as tmpdir:
            fitspath = os.path.join(tmpdir, filename)
            fits.write_sky_map(fitspath, skymap, nest=True)
            return open(fitspath, 'rb').read()
    except events.DetectorDisabledError:
        raise Ignore()
    except:  # noqa
        # Produce log message for any otherwise uncaught exception
        log.exception("sky localization failed")
        raise
    finally:
        log.removeHandler(handler)
        del handler
