"""Rapid sky localization with :mod:`BAYESTAR <ligo.skymap.bayestar>`."""
import io
import logging
import urllib.parse

from celery.exceptions import Ignore
from ligo.gracedb.logging import GraceDbLogHandler
from ligo.skymap import bayestar as _bayestar
from ligo.skymap.io import events
from ligo.skymap.io import fits

from .. import app
from . import gracedb

log = logging.getLogger('BAYESTAR')


@app.task(queue='openmp', shared=False)
def localize(coinc_psd, graceid, filename='bayestar.fits.gz',
             disabled_detectors=None):
    """Generate a rapid sky localization using
    :mod:`BAYESTAR <ligo.skymap.bayestar>`.

    Parameters
    ----------
    coinc_psd : tuple
        Tuple consisting of the byte contents of the input event's
        ``coinc.xml`` and ``psd.xml.gz`` files.
    graceid : str
        The GraceDB ID, used for FITS metadata and recording log messages
        to GraceDB.
    filename : str, optional
        The name of the FITS file.
    disabled_detectors : list, optional
        List of detectors to disable.

    Returns
    -------
    bytes
        The byte contents of the finished FITS file.

    Notes
    -----

    This task is adapted from the command-line tool
    :doc:`bayestar-localize-lvalert
    <ligo/skymap/tool/bayestar_localize_lvalert>`.

    It should execute in a special queue for computationally intensive,
    multithreaded, OpenMP tasks.
    """
    handler = GraceDbLogHandler(gracedb.client, graceid)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)

    # Determine the base URL for event pages.
    scheme, netloc, *_ = urllib.parse.urlparse(gracedb.client._service_url)
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
        skymap = _bayestar.localize(event)
        skymap.meta['objid'] = str(graceid)
        skymap.meta['url'] = '{}/{}'.format(base_url, graceid)
        log.info("sky localization complete")

        with io.BytesIO() as f:
            fits.write_sky_map(f, skymap, moc=True)
            return f.getvalue()
    except events.DetectorDisabledError:
        raise Ignore()
    except:  # noqa
        # Produce log message for any otherwise uncaught exception
        log.exception("sky localization failed")
        raise
    finally:
        log.removeHandler(handler)
        del handler
