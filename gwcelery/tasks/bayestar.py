import io
import logging
import os

from celery import group

from ..celery import app
from .gracedb import download, upload

# Workaround for testing in an environment that lacks LALInference
try:
    from lalinference.io.events import DetectorDisabledError
except ImportError:  # pragma: no cover
    DetectorDisabledError = ValueError

log = logging.getLogger('BAYESTAR')


def bayestar(graceid, service):
    """Peform rapid sky localization with BAYESTAR."""
    coinc = download('coinc.xml', graceid, service)
    psd = download('psd.xml.gz', graceid, service)
    coinc_psd = (coinc, psd)
    return group(
        localize.s(coinc_psd, graceid, service)
        | upload.s('bayestar.fits.gz', graceid, service,
                   'sky localization complete', 'sky_loc'),
        localize.s(coinc_psd, graceid, service,
                            disabled_detectors=['V1'],
                            filename='bayestar_no_virgo.fits.gz')
        | upload.s('bayestar_no_virgo.fits.gz', graceid, service,
                   'sky localization complete', 'sky_loc'))


# FIXME: should be `throws=events.DetectorDisabledError, but that would add
# a real on lalinference.
@app.task(queue='openmp', shared=False, throws=DetectorDisabledError)
def localize(coinc_psd, graceid, service, filename='bayestar.fits.gz',
                      disabled_detectors=None):
    from lalinference.io import events
    from lalinference.io import fits
    from lalinference.bayestar.command import TemporaryDirectory
    from lalinference.bayestar.sky_map import localize, rasterize
    from ligo.gracedb.logging import GraceDbLogHandler
    from ligo.gracedb.rest import GraceDb

    handler = GraceDbLogHandler(GraceDb(service), graceid)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)

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
        skymap = rasterize(localize(event))
        skymap.meta['objid'] = str(graceid)
        log.info("sky localization complete")

        with TemporaryDirectory() as tmpdir:
            fitspath = os.path.join(tmpdir, filename)
            fits.write_sky_map(fitspath, skymap, nest=True)
            return open(fitspath, 'rb').read()
    except:
        # Produce log message for any otherwise uncaught exception
        log.exception("sky localization failed")
        raise
    finally:
        log.removeHandler(handler)
        del handler
