"""Tasks that comprise the alert orchestrator, which responsible for the
vetting and annotation workflow to produce preliminary, initial, and update
alerts for gravitational-wave event candidates."""
import json
from urllib.error import URLError

from celery import chain, group
from ligo.gracedb.rest import HTTPError

from ..import app
from . import bayestar
from . import circulars
from .core import identity
from . import detchar
from . import em_bright
from . import gcn
from . import gracedb
from . import lvalert
from . import skymaps
from . import p_astro_gstlal


@lvalert.handler('superevent',
                 'mdc_superevent',
                 'test_superevent',
                 shared=False)
def handle_superevent(alert):
    """Schedule annotations for new superevents.

    After waiting for a time specified by the
    :obj:`~gwcelery.conf.orchestrator_timeout` configuration variable
    for the choice of preferred event to settle down, this task peforms data
    quality checks with :meth:`gwcelery.tasks.detchar.check_vectors` and
    calls :meth:`~gwcelery.tasks.orchestrator.preliminary_alert` to send a
    preliminary GCN notice.
    """

    if alert['alert_type'] != 'new':
        return

    superevent_id = alert['object']['superevent_id']
    start = alert['object']['t_start']
    end = alert['object']['t_end']

    (
        _get_preferred_event.si(superevent_id).set(
            countdown=app.conf['orchestrator_timeout']
        )
        |
        gracedb.get_event.s()
        |
        detchar.check_vectors.s(superevent_id, start, end)
        |
        preliminary_alert.s(superevent_id)
    ).apply_async()


@lvalert.handler('cbc_gstlal',
                 'cbc_gstlal-spiir',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 'test_gstlal',
                 'test_gstlal-spiir',
                 'test_pycbc',
                 'test_mbtaonline',
                 shared=False)
def handle_cbc_event(alert):
    """Peform annotations for CBC events that depend on pipeline-specific
    matched-filter parameter estimates.

    Notes
    -----

    This LVAlert message handler is triggered by updates that include the files
    ``psd.xml.gz`` and ``ranking_data.xml.gz``. The table below lists which
    files are created as a result, and which tasks generate them.

    ============================== =====================================================
    File                           Task
    ============================== =====================================================
    ``bayestar.fits.gz``           :meth:`gwcelery.tasks.bayestar.localize`
    ``source_classification.json`` :meth:`gwcelery.tasks.em_bright.classifier`
    ``p_astro_gstlal.json``        :meth:`gwcelery.tasks.p_astro_gstlal.compute_p_astro`
    ============================== =====================================================
    """  # noqa: E501

    if alert['alert_type'] != 'update':
        return

    graceid = alert['uid']
    filename = alert.get('file')

    if filename == 'psd.xml.gz':
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
    elif filename == 'ranking_data.xml.gz':
        (
            gracedb.get_event.s(graceid)
            |
            group(
                gracedb.download.si('coinc.xml', graceid),
                gracedb.download.si('ranking_data.xml.gz', graceid)
            )
            |
            p_astro_gstlal.compute_p_astro.s()
            |
            gracedb.upload.s(
                'p_astro_gstlal.json', graceid,
                'p_astro computation complete'
            )
            |
            gracedb.create_label.si('PASTRO_READY', graceid)
        ).delay()


@app.task(autoretry_for=(HTTPError, URLError, TimeoutError),
          default_retry_delay=20.0, retry_backoff=True,
          retry_kwargs=dict(max_retries=500), shared=False)
def _download(*args, **kwargs):
    """Download a file from GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.download`, except that
    it is retried for both :class:`TimeoutError` and
    :class:`~urllib.error.URLError`. In particular, it will be retried for 404
    (not found) errors."""
    return gracedb.download(*args, **kwargs)


@gracedb.task(shared=False)
def _get_preferred_event(superevent_id):
    """Determine preferred event for a superevent by querying GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.get_superevent`, except
    that it returns only the preferred event, and not the entire GraceDb JSON
    response."""
    return gracedb.get_superevent(superevent_id)['preferred_event']


@gracedb.task(shared=False)
def _create_voevent(em_bright_json, *args, **kwargs):
    """Create a VOEvent record from an EM bright JSON file.

    Parameters
    ----------
    em_bright_json : str, bytes, None
        The JSON contents of a source classification file generated by
        :meth:`gwcelery.tasks.em_bright.classifier`, or None
    \*args
        Additional positional arguments passed to
        :meth:`gwcelery.tasks.gracedb.create_voevent`.
    \*\*kwargs
        Additional keyword arguments passed to
        :meth:`gwcelery.tasks.gracedb.create_voevent`.

    Returns
    -------
    str
        The filename of the newly created VOEvent.
    """
    kwargs = dict(kwargs)
    if em_bright_json is not None:
        data = json.loads(em_bright_json)
        kwargs['ProbHasNS'] = 0.01 * data['Prob NS2']
        kwargs['ProbHasRemnant'] = 0.01 * data['Prob EMbright']
    return gracedb.create_voevent(*args, **kwargs)


@app.task(ignore_result=True, shared=False)
def preliminary_alert(event, superevent_id):
    """Produce a preliminary alert by copying any sky maps.

    This consists of the following steps:

    1.   Copy any sky maps and source classification from the preferred event
         to the superevent.
    2.   Create standard annotations for sky maps including all-sky plots by
         calling :meth:`gwcelery.tasks.skymaps.annotate_fits`.
    3.   Create a preliminary VOEvent.
    4.   Send the VOEvent to GCN.
    5.   Apply the GCN_PRELIM_SENT label to the superevent.
    6.   Create and upload a GCN Circular draft.
    """
    preferred_event_id = event['graceid']

    if event['group'] == 'CBC':
        skymap_filename = 'bayestar.fits.gz'
        skymap_image_filename = 'bayestar.png'
        skymap_type = 'BAYESTAR'
    elif event['pipeline'] == 'CWB':
        skymap_filename = 'skyprobcc_cWB.fits'
        skymap_image_filename = 'skyprobcc_cWB.png'
        skymap_type = 'CWB'
    elif event['pipeline'] == 'LIB':
        skymap_filename = 'LIB.fits.gz'
        skymap_image_filename = 'LIB.png'
        skymap_type = 'LIB'
    else:
        skymap_filename = skymap_type = skymap_image_filename = None

    # Start with a blank canvas (literally).
    canvas = chain()

    # If there is a sky map, then copy it to the superevent and create plots.
    if skymap_filename is not None:
        canvas |= (
            _download.s(skymap_filename, preferred_event_id)
            |
            group(
                gracedb.upload.s(
                    skymap_filename,
                    superevent_id,
                    message='{} localization copied from {}'.format(
                        skymap_type, preferred_event_id),
                    tags=['sky_loc', 'lvem']
                )
                |
                gracedb.create_label.si('SKYMAP_READY', superevent_id),

                skymaps.annotate_fits(
                    skymap_filename,
                    skymap_filename.partition('.fits')[0],
                    superevent_id,
                    ['sky_loc', 'lvem']
                )
            )
        )

    # If this is a CBC event, then copy the EM bright classification.
    if event['group'] == 'CBC':
        canvas |= (
            _download.si('source_classification.json', preferred_event_id)
            |
            gracedb.upload.s(
                'source_classification.json',
                superevent_id,
                message='Source classification copied from {}'.format(
                    preferred_event_id),
                tags=['em_bright', 'lvem']
            )
            |
            gracedb.create_label.si('EMBRIGHT_READY', superevent_id)
            |
            _download.si('source_classification.json', superevent_id)
        )
    else:
        canvas |= identity.si(None)

    # Send GCN notice and upload GCN circular draft.
    canvas |= (
        _create_voevent.s(
            superevent_id, 'preliminary',
            skymap_type=skymap_type,
            skymap_filename=skymap_filename,
            skymap_image_filename=skymap_image_filename
        )
        |
        group(
            gracedb.download.s(superevent_id)
            |
            gcn.send.s()
            |
            gracedb.create_label.si('GCN_PRELIM_SENT', superevent_id),

            circulars.create_circular.si(superevent_id)
            |
            gracedb.upload.s(
                'circular.txt',
                superevent_id,
                'Automated circular'
            )
        )
    )

    canvas.apply_async()
