"""Routing of LVAlert messages to other tasks."""
from urllib.error import URLError

from celery import group

from ..celery import app
# from . import circulars
from . import gracedb
from . import lvalert
from . import raven
from . import skymaps


@lvalert.handler('superevent',
                 'test_superevent',
                 shared=False)
def handle(alert):
    """Schedule annotations for new superevents.

    This task calls
    :func:`~gwcelery.tasks.orchestrator.annotate_superevent` after a timeout
    specified by the :obj:`~gwcelery.celery.Base.orchestrator_timeout`
    configuration variable.
    """

    if alert['alert_type'] != 'new':
        return

    superevent_id = alert['object']['superevent_id']
    (
        get_preferred_event.s(superevent_id) |
        annotate_superevent.s(superevent_id)
    ).apply_async(countdown=app.conf['orchestrator_timeout'])


@lvalert.handler('superevent',
                 'external_fermi',
                 'external_fermi_grb',
                 'external_grb',
                 'external_snews',
                 'external_snews_supernova',
                 'external_swift',
                 shared=False)
def handle_superevents_externaltriggers(alert):
    """Parse an LVAlert message related to superevents/external triggers and
    dispatch it to other tasks."""
    # Determine GraceDb ID
    graceid = alert['uid']

    if alert['alert_type'] == 'new':
        raven.coincidence_search(graceid, alert['object']).delay()


@app.task(autoretry_for=(URLError, TimeoutError), default_retry_delay=20.0,
          retry_backoff=True, retry_kwargs=dict(max_retries=500), shared=False)
def download(*args, **kwargs):
    """Download a file from GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.download`, except that
    it is retried for both `TimeoutError` and `URLError`. In particular, it
    will be retried for 404 (not found) errors.

    FIXME: Is there a way to change retry settings when calling a task,
    instead of creating an entirely new task?"""
    return gracedb.download(*args, **kwargs)


@app.task(autoretry_for=(URLError, TimeoutError), default_retry_delay=1.0,
          retry_backoff=True, retry_backoff_max=10.0,
          retry_kwargs=dict(max_retries=10), shared=False)
def get_preferred_event(superevent_id):
    """Determine preferred event for a superevent by querying GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.get_superevent`, except
    that it returns only the preferred event, and not the entire GraceDb JSON
    response."""
    return gracedb.get_superevent(superevent_id)['preferred_event']


@app.task(ignore_result=True, shared=False)
def annotate_superevent(preferred_event_id, superevent_id):
    """Perform annotations for a new superevent."""
    (
        download.s('bayestar.fits.gz', preferred_event_id)
        |
        group(
            gracedb.upload.s(
                'bayestar.fits.gz',
                superevent_id,
                message='BAYESTAR localization copied from {}'.format(
                    preferred_event_id),
                tags=['sky_loc', 'lvem']
            ),

            skymaps.annotate_fits(
                'bayestar.fits.gz',
                'bayestar',
                superevent_id,
                ['sky_loc', 'lvem']
            )
        )
        |
        gracedb.create_voevent.si(
            superevent_id, 'preliminary',
            skymap_type='BAYESTAR',
            skymap_filename='bayestar.fits.gz',
            skymap_image_filename='bayestar.png'
        )
        # FIXME: Circulars don't work yet due to a regression in ligo-gracedb.
        # See https://git.ligo.org/lscsoft/gracedb-client/issues/7
        #
        # |
        # circulars.create_circular.si(superevent_id)
        # |
        # gracedb.upload.s(
        #     'circular.txt',
        #     superevent_id,
        #     'Automated circular'
        # )
    ).delay()
