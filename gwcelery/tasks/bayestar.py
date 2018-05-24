"""Rapid sky localization with BAYESTAR."""
import io
import logging
import os
import tempfile

from celery import group
from celery.exceptions import Ignore
from ligo.gracedb.logging import GraceDbLogHandler
from ligo.skymap import bayestar as _bayestar
from ligo.skymap.io import events
from ligo.skymap.io import fits

from ..celery import app
from . import gracedb

log = logging.getLogger('BAYESTAR')


def bayestar(graceid):
    """Peform end-to-end rapid sky localization with BAYESTAR, including
    GraceDB downloads and uploads.

    This function downloads all of the required inputs for BAYESTAR,
    runs rapid sky localization with a few different detector settings,
    and uploads the resulting sky map FITS files to GraceDB.

    Internally, all of the heavy lifting is done by :meth:`localize`.
    """
    # FIXME: should call like this:
    #
    #     group(
    #         download.s('coinc.xml', ...),
    #         download.s('psd.xml.gz', ...)
    #     ) | group(
    #         localize.s(...) |
    #         upload.s(...) |
    #         ...,
    #         localize.s(...) |
    #         upload.s(...) |
    #         ...,
    #     )
    #
    # but groups do not preserve order. See:
    # https://github.com/celery/celery/issues/3781
    coinc = gracedb.download('coinc.xml', graceid)
    psd = gracedb.download('psd.xml.gz', graceid)
    coinc_psd = (coinc, psd)
    return group(
        localize.s(coinc_psd, graceid) |
        gracedb.upload.s('bayestar.fits.gz', graceid,
                         'sky localization complete', ['sky_loc', 'lvem']),
        localize.s(coinc_psd, graceid,
                   disabled_detectors=['V1'],
                   filename='bayestar_no_virgo.fits.gz') |
        gracedb.upload.s('bayestar_no_virgo.fits.gz', graceid,
                         'sky localization complete', ['sky_loc', 'lvem']))


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
