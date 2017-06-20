import io
import os

from ..celery import app


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
