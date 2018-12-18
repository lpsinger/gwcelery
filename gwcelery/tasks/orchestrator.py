"""Tasks that comprise the alert orchestrator, which responsible for the
vetting and annotation workflow to produce preliminary, initial, and update
alerts for gravitational-wave event candidates."""
import json
import re
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
from . import lalinference
from . import lvalert
from . import skymaps
from . import p_astro_gstlal, p_astro_other


@lvalert.handler('superevent',
                 'mdc_superevent',
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

    superevent_id = alert['uid']

    if alert['alert_type'] == 'new':
        start = alert['object']['t_start']
        end = alert['object']['t_end']

        gracedb.create_label.s('ADVREQ', superevent_id).apply_async()

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
    # check DQV label on superevent, run check_vectors if required
    elif alert['alert_type'] == 'event_added':
        # FIXME Getting the graceid from the most recent event added log
        # this is a temporary solution, fix post ER13
        regex = re.compile(r'Added event: ([GMT][0-9]+)')
        for log in reversed(gracedb.get_log(superevent_id)):
            match = regex.match(log['comment'])
            if match:
                new_event_id = match[1]
                break
        else:
            raise ValueError('Added event log message not found')

        start = alert['data']['t_start']
        end = alert['data']['t_end']

        if 'DQV' in gracedb.get_labels(superevent_id):
            (
                detchar.check_vectors.s(new_event_id, superevent_id,
                                        start, end)
                |
                _update_if_dqok.si(superevent_id, new_event_id)
            ).apply_async()

    elif alert['alert_type'] == 'label_added':
        label_name = alert['data']['name']
        if label_name == 'ADVOK':
            initial_alert(superevent_id)
        elif label_name == 'ADVNO':
            retraction_alert(superevent_id)


@lvalert.handler('cbc_gstlal',
                 'cbc_spiir',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
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
    ``bayestar.fits``              :meth:`gwcelery.tasks.bayestar.localize`
    ``source_classification.json`` :meth:`gwcelery.tasks.em_bright.classifier`
    ``p_astro.json``        :meth:`gwcelery.tasks.p_astro_gstlal.compute_p_astro`
    ============================== =====================================================
    """  # noqa: E501

    graceid = alert['uid']

    # p_astro calculation for other pipelines
    if alert['alert_type'] == 'new' \
            and (alert['object']['pipeline'].lower() != 'gstlal'
                 or alert['object']['search'] == 'MDC'):
        extra_attributes = alert['object']['extra_attributes']
        snr = extra_attributes['CoincInspiral']['snr']
        far = alert['object']['far']
        mass1 = extra_attributes['SingleInspiral'][0]['mass1']
        mass2 = extra_attributes['SingleInspiral'][0]['mass2']
        (
            p_astro_other.compute_p_astro.s(snr, far, mass1, mass2)
            |
            gracedb.upload.s(
                'p_astro.json', graceid,
                'p_astro computation complete'
            )
            |
            gracedb.create_label.si('PASTRO_READY', graceid)
        ).delay()

    if alert['alert_type'] != 'log':
        return

    filename = alert['data']['filename']

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
                    'bayestar.fits', graceid,
                    'sky localization complete', ['sky_loc', 'public']
                )
                |
                gracedb.create_label.si('SKYMAP_READY', graceid),

                em_bright.classifier.s(graceid)
                |
                gracedb.upload.s(
                    'source_classification.json', graceid,
                    'source classification complete', ['em_bright', 'public']
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
                'p_astro.json', graceid,
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


@app.task(shared=False, ignore_result=True)
def _update_if_dqok(superevent_id, event_id):
    """Update `preferred_event` of `superevent_id` to `event_id`
    if `DQOK` label has been applied
    """
    if 'DQOK' in gracedb.get_labels(superevent_id):
        gracedb.update_superevent(superevent_id, preferred_event=event_id)
        gracedb.create_log(
            "DQOK applied based on new event %s" % (event_id), superevent_id)


@gracedb.task(shared=False)
def _get_preferred_event(superevent_id):
    """Determine preferred event for a superevent by querying GraceDb.

    This works just like :func:`gwcelery.tasks.gracedb.get_superevent`, except
    that it returns only the preferred event, and not the entire GraceDb JSON
    response."""
    return gracedb.get_superevent(superevent_id)['preferred_event']


@gracedb.task(shared=False)
def _create_voevent(properties_and_classification_json, *args, **kwargs):
    r"""Create a VOEvent record from an EM bright JSON file.

    Parameters
    ----------
    properties_and_classification_json : tuple, None
        A tuple of two JSON strings, generated by
        :meth:`gwcelery.tasks.em_bright.classifier` and
        :meth:`gwcelery.tasks.p_astro_gstlal.compute_p_astro` respectively; or
        None
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

    if properties_and_classification_json is not None:
        data = {}
        for text in properties_and_classification_json:
            data.update(json.loads(text))

        kwargs['ProbHasNS'] = 0.01 * data['Prob NS2']
        kwargs['ProbHasRemnant'] = 0.01 * data['Prob EMbright']
        kwargs['BNS'] = data['BNS']
        kwargs['NSBH'] = data['NSBH']
        kwargs['BBH'] = data['BBH']
        kwargs['Terrestrial'] = data['Terr']

    skymap_filename = kwargs.get('skymap_filename')
    if skymap_filename is not None:
        skymap_type = re.sub(r'\.fits(\..+)?$', '', skymap_filename)
        kwargs.setdefault('skymap_type', skymap_type)
        kwargs.setdefault('skymap_image_filename', skymap_type + '.png')

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
    7.   Start parameter estimation with LALInference.
    """
    preferred_event_id = event['graceid']

    if event['group'] == 'CBC':
        skymap_filename = 'bayestar.fits'
    elif event['pipeline'] == 'CWB':
        skymap_filename = 'cWB.fits.gz'
    elif event['pipeline'] == 'oLIB':
        skymap_filename = 'oLIB.fits.gz'
    else:
        skymap_filename = None

    original_skymap_filename = skymap_filename
    if skymap_filename.endswith('.fits'):
        skymap_filename += '.gz'

    # Make the event public.
    # FIXME: For ER13, only expose mock events.
    if event['search'] == 'MDC':
        canvas = gracedb.expose.s(superevent_id)
    else:
        canvas = chain()

    # If there is a sky map, then copy it to the superevent and create plots.
    if skymap_filename is not None:
        canvas |= (
            _download.si(original_skymap_filename, preferred_event_id)
            |
            group(
                gracedb.upload.s(
                    original_skymap_filename,
                    superevent_id,
                    message='Localization copied from {}'.format(
                        preferred_event_id),
                    tags=['sky_loc', 'public']
                )
                |
                _download.si(original_skymap_filename, superevent_id)
                |
                skymaps.flatten.s(skymap_filename)
                |
                gracedb.upload.s(
                    skymap_filename,
                    superevent_id,
                    message='Flattened from multiresolution file {}'.format(
                        original_skymap_filename),
                    tags=['sky_loc', 'public']
                )
                |
                gracedb.create_label.si('SKYMAP_READY', superevent_id),

                skymaps.annotate_fits(
                    original_skymap_filename,
                    superevent_id,
                    ['sky_loc', 'public']
                )
            )
        )

    # If this is a CBC event, then copy the EM bright classification.
    if event['group'] == 'CBC':
        canvas |= group(
            _download.si('source_classification.json', preferred_event_id)
            |
            gracedb.upload.s(
                'source_classification.json',
                superevent_id,
                message='Source properties copied from {}'.format(
                    preferred_event_id),
                tags=['em_bright', 'public']
            )
            |
            gracedb.create_label.si('EMBRIGHT_READY', superevent_id)
            |
            _download.si('source_classification.json', superevent_id),

            _download.si('p_astro.json', preferred_event_id)
            |
            gracedb.upload.s(
                'p_astro.json',
                superevent_id,
                message='Source classification copied from {}'.format(
                    preferred_event_id),
                tags=['em_bright', 'public']
            )
            |
            gracedb.create_label.si('PASTRO_READY', superevent_id)
            |
            _download.si('p_astro.json', superevent_id)
        ) | identity.s()  # FIXME: necessary to pass result to next task?
    else:
        canvas |= identity.si(None)

    # Send GCN notice and upload GCN circular draft for online events.
    trials_factor = \
        app.conf['preliminary_alert_trials_factor'][event['group'].lower()]
    if not event['offline'] \
            and trials_factor * event['far'] <= \
            app.conf['preliminary_alert_far_threshold'] \
            and 'DQV' not in gracedb.get_labels(superevent_id):
        canvas |= (
            _create_voevent.s(
                superevent_id, 'preliminary',
                skymap_filename=skymap_filename,
                # FIXME: for ER13, only send public alerts for MDC events.
                internal=(event['search'] != 'MDC'),
                open_alert=True
            )
            |
            group(
                gracedb.download.s(superevent_id)
                |
                gcn.send.s()
                |
                gracedb.create_label.si('GCN_PRELIM_SENT', superevent_id),

                # FIXME: after ER13, we need to add the 'public' tag to make
                # the VOEvent file public in GraceDb, like we do for the
                # initial, update, and retraction alerts.

                circulars.create_circular.si(superevent_id)
                |
                gracedb.upload.s(
                    'circular.txt',
                    superevent_id,
                    'Automated circular'
                )
            )
        )

        if event['group'] == 'CBC' and event['search'] != 'MDC':
            # Start parameter estimation.
            lalinference.lalinference.delay(preferred_event_id, superevent_id)

    canvas.apply_async()


@app.task(ignore_result=True, shared=False)
def initial_or_update_alert(superevent_id, alert_type, skymap_filename=None):
    """
    Create and send initial or update GCN notice.

    Parameters
    ----------
    superevent_id : str
        The superevent ID.
    alert_type : {'initial', 'update'}
        The alert type.
    skymap_filename :str, optional
        The sky map to send. If None, then most recent public sky map is used.
    """
    if skymap_filename is None:
        for message in gracedb.get_log(superevent_id):
            t = message['tag_names']
            f = message['filename']
            if {'sky_loc', 'public'}.issubset(t) and f \
                    and (f.endswith('.fits') or f.endswith('.fits.gz')):
                skymap_filename = f

    (
        gracedb.expose.s(superevent_id)
        |
        group(
            gracedb.download.si('source_classification.json', superevent_id),
            gracedb.download.si('p_astro.json', superevent_id)
        )
        |
        _create_voevent.s(
            superevent_id,
            alert_type,
            skymap_filename=skymap_filename,
            internal=False,
            open_alert=True,
            vetted=True
        )
        |
        group(
            gracedb.download.s(superevent_id)
            |
            gcn.send.s(),

            gracedb.create_tag.s('public', superevent_id)
        )
    ).apply_async()


@app.task(ignore_result=True, shared=False)
def initial_alert(superevent_id, skymap_filename=None):
    """Produce an initial alert.

    This does nothing more than call
    :meth:`~gwcelery.tasks.orchestrator.initial_or_update_alert` with
    ``alert_type='initial'``.

    Parameters
    ----------
    superevent_id : str
        The superevent ID.
    skymap_filename :str, optional
        The sky map to send. If None, then most recent public sky map is used.
    """
    initial_or_update_alert(superevent_id, 'initial', skymap_filename)


@app.task(ignore_result=True, shared=False)
def update_alert(superevent_id, skymap_filename=None):
    """Produce an update alert.

    This does nothing more than call
    :meth:`~gwcelery.tasks.orchestrator.initial_or_update_alert` with
    ``alert_type='update'``.

    Parameters
    ----------
    superevent_id : str
        The superevent ID.
    skymap_filename :str, optional
        The sky map to send. If None, then most recent public sky map is used.
    """
    initial_or_update_alert(superevent_id, 'update', skymap_filename)


@app.task(ignore_result=True, shared=False)
def retraction_alert(superevent_id):
    """Produce a retraction alert. This is currently just a stub and does
    nothing more than create and send a VOEvent."""
    (
        gracedb.expose.s(superevent_id)
        |
        gracedb.create_voevent.si(
            superevent_id, 'retraction',
            internal=False,
            open_alert=True,
            vetted=True
        )
        |
        group(
            gracedb.download.s(superevent_id)
            |
            gcn.send.s(),

            gracedb.create_tag.s('public', superevent_id)
        )
    ).apply_async()
