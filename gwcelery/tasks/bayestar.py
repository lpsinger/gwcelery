import io
import logging
import os

from ..celery import app

log = logging.getLogger('BAYESTAR')


@app.task(queue='openmp')
def bayestar(coinc_psd, graceid, service):
    from lalinference.io.events import ligolw
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
        event, = ligolw.open(coinc, psd_file=psd, coinc_def=None).values()

        # Run BAYESTAR
        log.info("starting sky localization")
        skymap = rasterize(localize(event))
        skymap.meta['objid'] = str(graceid)
        log.info("sky localization complete")

        with TemporaryDirectory() as tmpdir:
            fitspath = os.path.join(tmpdir, 'bayestar.fits.gz')
            fits.write_sky_map(fitspath, skymap, nest=True)
            return open(fitspath, 'rb').read()
    finally:
        log.removeHandler(handler)
        del handler
