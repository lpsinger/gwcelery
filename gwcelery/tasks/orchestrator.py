"""Routing of LVAlert messages to other tasks."""
import json
from urllib.error import URLError

from celery import group
from celery.exceptions import Ignore
from ligo.gracedb.rest import HTTPError

from ..celery import app
from . import bayestar
from . import circulars
from .core import identity
from . import detchar
from . import em_bright
from . import gcn
from . import gracedb
from . import lvalert
from . import raven
from . import skymaps


@lvalert.handler('superevent',
                 'test_superevent',
                 shared=False)
def handle_superevent(alert):
    """Schedule annotations for new superevents.

    This task calls
    :func:`~gwcelery.tasks.orchestrator.annotate_cbc_superevent` after a
    timeout specified by the :obj:`~gwcelery.celery.Base.orchestrator_timeout`
    configuration variable.
    """

    if alert['alert_type'] != 'new':
        return

    superevent_id = alert['object']['superevent_id']
    start = alert['object']['t_start']
    end = alert['object']['t_end']

    (
        get_preferred_event.si(superevent_id).set(
            countdown=app.conf['orchestrator_timeout']
        )
        |
        gracedb.get_event.s()
        |
        detchar.check_vectors.s(superevent_id, start, end)
        |
        group(
            continue_if_group_is.s('CBC')
            |
            annotate_cbc_superevent.s(superevent_id),

            continue_if_group_is.s('Burst')
            |
            annotate_burst_superevent.s(superevent_id)
        )
    ).apply_async()


@lvalert.handler('cbc_gstlal',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 'test_gstlal',
                 'test_pycbc',
                 'test_mbtaonline',
                 shared=False)
def handle_cbc_event(alert):
    """Peform annotations for CBC events that depend on pipeline-specific
    matched-filter parameter estimates, including preliminary sky localization
    with BAYESTAR (via the :meth:`gwcelery.tasks.bayestar.localize` task) and
    preliminary source classification (via the
    :meth:`gwcelery.tasks.em_bright.em_bright` task)."""

    # Only handle alerts for the upload of a PSD file.
    if alert['alert_type'] != 'update' or alert.get('file') != 'psd.xml.gz':
        return

    graceid = alert['uid']

    (
        group(
            gracedb.download.s('coinc.xml', graceid),
            gracedb.download.s('psd.xml.gz', graceid)
        )
        |
        # FIXME: group(A, B) | group(C, D) does not pass the results from
        # tasks A and B to tasks C and D without this.
        identity.s()
        |
        group(
            bayestar.localize.s(graceid)
            |
            gracedb.upload.s(
                'bayestar.fits.gz', graceid,
                'sky localization complete', ['sky_loc', 'lvem']
            )
            |
            gracedb.create_label.si('SKYMAP_READY', graceid),

            em_bright.classifier.s(graceid)
            |
            gracedb.upload.s(
                'source_classification.json', graceid,
                'source classification complete', ['em_bright', 'lvem']
            )
            |
            gracedb.create_label.si('EMBRIGHT_READY', graceid)
        )
    ).delay()


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


@app.task(autoretry_for=(HTTPError, URLError, TimeoutError),
          default_retry_delay=20.0, retry_backoff=True,
          retry_kwargs=dict(max_retries=500), shared=False)
def download(*args, **kwargs):
    """Download a file from GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.download`, except that
    it is retried for both `TimeoutError` and `URLError`. In particular, it
    will be retried for 404 (not found) errors.

    FIXME: Is there a way to change retry settings when calling a task,
    instead of creating an entirely new task?"""
    return gracedb.download(*args, **kwargs)


@gracedb.task
def get_preferred_event(superevent_id):
    """Determine preferred event for a superevent by querying GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.get_superevent`, except
    that it returns only the preferred event, and not the entire GraceDb JSON
    response."""
    return gracedb.get_superevent(superevent_id)['preferred_event']


@app.task(shared=False)
def continue_if_group_is(event, group):
    """Continue processing if an event's group matches `group`, else halt
    the rest of the canvas."""
    if event['group'].lower() == group.lower():
        return event
    else:
        raise Ignore('This is not a {} event.'.format(group))


@gracedb.task
def create_voevent_for_em_bright(em_bright_json, *args, **kwargs):
    """Create a VOEvent record from an EM bright JSON file."""
    data = json.loads(em_bright_json)
    return gracedb.create_voevent(*args, **kwargs,
                                  ProbHasNS=0.01 * data['Prob NS2'],
                                  ProbHasRemnant=0.01 * data['Prob EMbright'])


@app.task(ignore_result=True, shared=False)
def annotate_burst_superevent(event, superevent_id):
    """Perform annotations for a superevent whose preferred event is a
    Burst."""
    (
        gracedb.create_voevent.s(superevent_id, 'preliminary')
        |
        group(
            circulars.create_circular.si(superevent_id),

            gracedb.download.s(superevent_id)
            |
            gcn.send.s()
            |
            gracedb.create_label.si('GCN_PRELIM_SENT', superevent_id)
        )
    ).delay()


@app.task(ignore_result=True, shared=False)
def annotate_cbc_superevent(event, superevent_id):
    """Perform annotations for a superevent whose preferred event is a CBC."""
    preferred_event_id = event['graceid']

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
            )
            |
            gracedb.create_label.si('SKYMAP_READY', superevent_id),

            skymaps.annotate_fits(
                'bayestar.fits.gz',
                'bayestar',
                superevent_id,
                ['sky_loc', 'lvem']
            )
        )
        |
        download.si('source_classification.json', preferred_event_id)
        |
        group(
            create_voevent_for_em_bright.s(
                superevent_id, 'preliminary',
                skymap_type='BAYESTAR',
                skymap_filename='bayestar.fits.gz',
                skymap_image_filename='bayestar.png'
            )
            |
            gracedb.download.s(superevent_id)
            |
            gcn.send.s()
            |
            gracedb.create_label.si('GCN_PRELIM_SENT', superevent_id),

            gracedb.upload.s(
                'source_classification.json',
                superevent_id,
                message='Source classification copied from {}'.format(
                    preferred_event_id),
                tags=['em_bright', 'lvem']
            )
            |
            gracedb.create_label.si('EMBRIGHT_READY', superevent_id),
        )
        |
        circulars.create_circular.si(superevent_id)
        |
        gracedb.upload.s(
            'circular.txt',
            superevent_id,
            'Automated circular'
        )
    ).delay()
