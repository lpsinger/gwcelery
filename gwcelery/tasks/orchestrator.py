"""Tasks that comprise the alert orchestrator, which responsible for the
vetting and annotation workflow to produce preliminary, initial, and update
alerts for gravitational-wave event candidates."""
import json
import re
from socket import gaierror
from urllib.error import URLError

from celery import chain, group
from ligo.gracedb.rest import HTTPError

from ..import app
from . import bayestar
from . import circulars
from .core import identity, ordered_group, ordered_group_first
from . import detchar
from . import em_bright
from . import gcn
from . import gracedb
from . import lalinference
from . import lvalert
from . import p_astro
from . import skymaps
from . import superevents


@lvalert.handler('cbc_gstlal',
                 'cbc_spiir',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 'burst_olib',
                 'burst_cwb',
                 shared=False)
def handle_selected_as_preferred(alert):
    # FIXME DQV & INJ labels not incorporated into labeling ADVREQ,
    # Remove after !495 is merged

    if alert['alert_type'] == 'selected_as_preferred':
        superevent_id = alert['object']['superevent']
        gracedb.create_label.delay('EM_Selected', superevent_id)

        if superevents.should_publish(alert['object']):
            gracedb.create_label.delay('ADVREQ', superevent_id)


@lvalert.handler('superevent',
                 'mdc_superevent',
                 shared=False)
def handle_superevent(alert):
    """Schedule annotations for new superevents.

    After waiting for a time specified by the
    :obj:`~gwcelery.conf.orchestrator_timeout` configuration variable
    for the choice of preferred event to settle down, this task performs data
    quality checks with :meth:`gwcelery.tasks.detchar.check_vectors` and
    calls :meth:`~gwcelery.tasks.orchestrator.preliminary_alert` to send a
    preliminary GCN notice.
    """
    superevent_id = alert['uid']
    # launch PE and detchar based on new type superevents
    if alert['alert_type'] == 'new':
        (
            _get_preferred_event.si(superevent_id).set(
                countdown=app.conf['pe_timeout']
            )
            |
            ordered_group(
                _get_lowest_far.si(superevent_id),
                gracedb.get_event.s()
            )
            |
            parameter_estimation.s(superevent_id)
        ).apply_async()

    elif alert['alert_type'] == 'label_added':
        label_name = alert['data']['name']
        # launch preliminary alert on EM_Selected
        if label_name == 'EM_Selected':
            (
                _get_preferred_event.si(superevent_id).set(
                    countdown=app.conf['orchestrator_timeout']
                )
                |
                gracedb.get_event.s()
                |
                detchar.check_vectors.s(
                    superevent_id,
                    alert['object']['t_start'],
                    alert['object']['t_end']
                )
                |
                preliminary_alert.s(superevent_id)
            ).apply_async()
        # launch initial/retraction alert on ADVOK/ADVNO
        elif label_name == 'ADVOK':
            initial_alert((None, None, None), superevent_id)
        elif label_name == 'ADVNO':
            retraction_alert(superevent_id)

    # check DQV label on superevent, run check_vectors if required
    elif alert['alert_type'] == 'event_added':
        new_event_id = alert['data']['preferred_event']
        start = alert['data']['t_start']
        end = alert['data']['t_end']

        if 'DQV' in gracedb.get_labels(superevent_id):
            (
                gracedb.get_event.s(new_event_id)
                |
                detchar.check_vectors.s(superevent_id, start, end)
                |
                _update_if_dqok.si(superevent_id, new_event_id)
            ).apply_async()


@lvalert.handler('cbc_gstlal',
                 'cbc_spiir',
                 'cbc_pycbc',
                 'cbc_mbtaonline',
                 shared=False)
def handle_cbc_event(alert):
    """Perform annotations for CBC events that depend on pipeline-specific
    matched-filter parameter estimates.

    Notes
    -----

    This LVAlert message handler is triggered by updates that include the file
    ``psd.xml.gz``. The table below lists which
    files are created as a result, and which tasks generate them.

    ============================== ================================================
    File                           Task
    ============================== ================================================
    ``em_bright.json``             :meth:`gwcelery.tasks.em_bright.classifier`
    ``p_astro.json.json``          :meth:`gwcelery.tasks.p_astro.compute_p_astro`
    ============================== ================================================
    """  # noqa: E501

    graceid = alert['uid']
    priority = 0 if superevents.should_publish(alert['object']) else 1

    # em_bright and p_astro calculation
    if alert['alert_type'] == 'new':
        pipeline = alert['object']['pipeline'].lower()
        instruments = superevents.get_instruments_in_ranking_statistic(
            alert['object'])
        extra_attributes = alert['object']['extra_attributes']
        snr = superevents.get_snr(alert['object'])
        far = alert['object']['far']
        mass1 = extra_attributes['SingleInspiral'][0]['mass1']
        mass2 = extra_attributes['SingleInspiral'][0]['mass2']
        chi1 = extra_attributes['SingleInspiral'][0]['spin1z']
        chi2 = extra_attributes['SingleInspiral'][0]['spin2z']

        em_bright_task = em_bright.classifier_gstlal if pipeline == 'gstlal' \
            else em_bright.classifier_other

        (
            em_bright_task.si((mass1, mass2, chi1, chi2, snr), graceid)
            |
            gracedb.upload.s(
                'em_bright.json', graceid,
                'em bright complete', ['em_bright', 'public']
            )
            |
            gracedb.create_label.si('EMBRIGHT_READY', graceid)
        ).apply_async(priority=priority)

        # p_astro calculation for other pipelines
        if pipeline != 'gstlal' or alert['object']['search'] == 'MDC':
            (
                p_astro.compute_p_astro.s(snr,
                                          far,
                                          mass1,
                                          mass2,
                                          pipeline,
                                          instruments)
                |
                gracedb.upload.s(
                    'p_astro.json', graceid,
                    'p_astro computation complete', ['p_astro', 'public']
                )
                |
                gracedb.create_label.si('PASTRO_READY', graceid)
            ).apply_async(priority=priority)


@lvalert.handler('superevent',
                 'mdc_superevent',
                 shared=False)
def handle_posterior_samples(alert):
    """Generate multi-resolution and flat-resolution fits files and skymaps
    from an uploaded HDF5 file containing posterior samples.
    """
    if alert['alert_type'] != 'log' or \
            not alert['data']['filename'].endswith('.posterior_samples.hdf5'):
        return
    superevent_id = alert['uid']
    filename = alert['data']['filename']
    prefix, _ = filename.rsplit('.posterior_samples.')
    # FIXME: It is assumed that posterior samples always come from
    # lalinference. After bilby or rift is integrated, this has to be fixed.
    (
        gracedb.download.si(filename, superevent_id)
        |
        skymaps.skymap_from_samples.s()
        |
        group(
            skymaps.annotate_fits.s(
                '{}.fits.gz'.format(prefix),
                superevent_id, ['pe', 'sky_loc']
            ),

            gracedb.upload.s(
                '{}.multiorder.fits'.format(prefix), superevent_id,
                'Multiresolution fits file generated from {}'.format(filename),
                ['pe', 'sky_loc']
            ),

            skymaps.flatten.s('{}.fits.gz'.format(prefix))
            |
            gracedb.upload.s(
                '{}.fits.gz'.format(prefix), superevent_id,
                'Flat-resolution fits file created from {}'.format(filename),
                ['pe', 'sky_loc']
            )
        )
    ).delay()


@app.task(autoretry_for=(gaierror, HTTPError, URLError, TimeoutError),
          default_retry_delay=20.0, retry_backoff=True,
          retry_kwargs=dict(max_retries=500), shared=False)
def _download(*args, **kwargs):
    """Download a file from GraceDB.

    This works just like :func:`gwcelery.tasks.gracedb.download`, except that
    it is retried for both :class:`TimeoutError` and
    :class:`~urllib.error.URLError`. In particular, it will be retried for 404
    (not found) errors."""
    # FIXME: remove ._orig_run when this bug is fixed:
    # https://github.com/getsentry/sentry-python/issues/370
    return gracedb.download._orig_run(*args, **kwargs)


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
    """Determine preferred event for a superevent by querying GraceDB.

    This works just like :func:`gwcelery.tasks.gracedb.get_superevent`, except
    that it returns only the preferred event, and not the entire GraceDB JSON
    response."""
    # FIXME: remove ._orig_run when this bug is fixed:
    # https://github.com/getsentry/sentry-python/issues/370
    return gracedb.get_superevent._orig_run(superevent_id)['preferred_event']


@gracedb.task(shared=False)
def _create_voevent(classification, *args, **kwargs):
    r"""Create a VOEvent record from an EM bright JSON file.

    Parameters
    ----------
    classification : tuple, None
        A collection of JSON strings, generated by
        :meth:`gwcelery.tasks.em_bright.classifier` and
        :meth:`gwcelery.tasks.p_astro.compute_p_astro` or
        content of ``p_astro.json`` uploaded by gstlal respectively;
        or None
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

    if classification is not None:
        # Merge source classification and source properties into kwargs.
        for text in classification:
            if text is not None:
                kwargs.update(json.loads(text))

    # FIXME: These keys have differ between em_bright.json
    # and the GraceDB REST API.
    try:
        kwargs['ProbHasNS'] = kwargs.pop('HasNS')
    except KeyError:
        pass

    try:
        kwargs['ProbHasRemnant'] = kwargs.pop('HasRemnant')
    except KeyError:
        pass

    skymap_filename = kwargs.get('skymap_filename')
    if skymap_filename is not None:
        skymap_type = re.sub(r'\.fits(\..+)?$', '', skymap_filename)
        kwargs.setdefault('skymap_type', skymap_type)

    # FIXME: remove ._orig_run when this bug is fixed:
    # https://github.com/getsentry/sentry-python/issues/370
    return gracedb.create_voevent._orig_run(*args, **kwargs)


@gracedb.task(shared=False)
def _create_label_and_return_filename(filename, label, graceid):
    gracedb.create_label(label, graceid)
    return filename


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
    priority = 0 if superevents.should_publish(event) else 1
    preferred_event_id = event['graceid']

    if event['group'] == 'CBC':
        skymap_filename = 'bayestar.multiorder.fits'
    elif event['pipeline'] == 'CWB':
        skymap_filename = 'cWB.fits.gz'
    elif event['pipeline'] == 'oLIB':
        skymap_filename = 'oLIB.fits.gz'
    else:
        skymap_filename = None

    original_skymap_filename = skymap_filename
    if skymap_filename.endswith('.multiorder.fits'):
        skymap_filename = skymap_filename.replace('.multiorder.fits', '.fits')
    if skymap_filename.endswith('.fits'):
        skymap_filename += '.gz'

    # Determine if the event should be made public.
    is_publishable = (superevents.should_publish(event)
                      and {'DQV', 'INJ'}.isdisjoint(event['labels']))

    canvas = chain()

    if event['group'] == 'CBC':
        canvas |= (
            ordered_group(
                gracedb.download.si('coinc.xml', preferred_event_id),
                _download.si('psd.xml.gz', preferred_event_id)
            )
            |
            bayestar.localize.s(preferred_event_id)
            |
            gracedb.upload.s(
                'bayestar.multiorder.fits', preferred_event_id,
                'sky localization complete', ['sky_loc', 'public']
            )
            |
            gracedb.create_label.si('SKYMAP_READY', preferred_event_id)
        )

    canvas |= ordered_group(
        (
            _download.si(original_skymap_filename, preferred_event_id)
            |
            ordered_group_first(
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
                _create_label_and_return_filename.s(
                    'SKYMAP_READY', superevent_id
                ),

                gracedb.upload.s(
                    original_skymap_filename,
                    superevent_id,
                    message='Localization copied from {}'.format(
                        preferred_event_id),
                    tags=['sky_loc', 'public']
                ),

                skymaps.annotate_fits.s(
                    skymap_filename,
                    superevent_id,
                    ['sky_loc', 'public']
                )
            )
        ) if skymap_filename is not None else identity.s(None),

        (
            _download.si('em_bright.json', preferred_event_id)
            |
            gracedb.upload.s(
                'em_bright.json',
                superevent_id,
                message='Source properties copied from {}'.format(
                    preferred_event_id),
                tags=['em_bright', 'public']
            )
            |
            _create_label_and_return_filename.s(
                'EMBRIGHT_READY', superevent_id
            )
        ) if event['group'] == 'CBC' else identity.s(None),

        (
            _download.si('p_astro.json', preferred_event_id)
            |
            gracedb.upload.s(
                'p_astro.json',
                superevent_id,
                message='Source classification copied from {}'.format(
                    preferred_event_id),
                tags=['p_astro', 'public']
            )
            |
            _create_label_and_return_filename.s(
                'PASTRO_READY', superevent_id
            )
        ) if event['group'] == 'CBC' else identity.s(None)
    )

    # Send GCN notice and upload GCN circular draft for online events.
    if is_publishable:
        canvas |= preliminary_initial_update_alert.s(
            superevent_id, 'preliminary')

    canvas.apply_async(priority=priority)


@gracedb.task(shared=False)
def _get_lowest_far(superevent_id):
    """Obtain the lowest FAR of the events contained in the target
    superevent"""
    # FIXME: remove ._orig_run when this bug is fixed:
    # https://github.com/getsentry/sentry-python/issues/370
    return min(gracedb.get_event._orig_run(gid)['far'] for gid in
               gracedb.get_superevent._orig_run(superevent_id)["gw_events"])


@app.task(ignore_result=True, shared=False)
def parameter_estimation(far_event, superevent_id):
    """Tasks for Parameter Estimation Followup with LALInference

    This consists of the following steps:

    1.   Prepare and upload an ini file which is suitable for the target event.
    2.   Start Parameter Estimation if FAR is smaller than the PE threshold.
    """
    far, event = far_event
    preferred_event_id = event['graceid']
    # FIXME: it will be better to start parameter estimation for 'burst'
    # events.
    if event['group'] == 'CBC' and event['search'] != 'MDC':
        canvas = lalinference.pre_pe_tasks(event, superevent_id)
        if far <= app.conf['pe_threshold']:
            canvas |= lalinference.start_pe.s(preferred_event_id,
                                              superevent_id)
        else:
            canvas |= gracedb.upload.si(
                          filecontents=None, filename=None,
                          graceid=superevent_id,
                          message='FAR is larger than the PE threshold, '
                                  '{}  Hz. Parameter Estimation will not '
                                  'start.'.format(app.conf['pe_threshold']),
                          tags='pe'
                      )

        canvas.apply_async()


@gracedb.task(ignore_result=True, shared=False)
def preliminary_initial_update_alert(filenames, superevent_id, alert_type):
    """
    Create and send a preliminary, initial, or update GCN notice.

    Parameters
    ----------
    filenames : tuple
        A list of the sky map, em_bright, and p_astro filenames.
    superevent_id : str
        The superevent ID.
    alert_type : {'preliminary', 'initial', 'update'}
        The alert type.

    Notes
    -----
    This function is decorated with :obj:`gwcelery.tasks.gracedb.task` rather
    than :obj:`gwcelery.app.task` so that a synchronous call to
    :func:`gwcelery.tasks.gracedb.get_log` is retried in the event of GraceDB
    API failures.
    """
    skymap_filename, em_bright_filename, p_astro_filename = filenames
    skymap_needed = (skymap_filename is None)
    em_bright_needed = (em_bright_filename is None)
    p_astro_needed = (p_astro_filename is None)
    if skymap_needed or em_bright_needed or p_astro_needed:
        for message in gracedb.get_log(superevent_id):
            t = message['tag_names']
            f = message['filename']
            v = message['file_version']
            fv = '{},{}'.format(f, v)
            if not f:
                continue
            if skymap_needed \
                    and {'sky_loc', 'public'}.issubset(t) \
                    and f.endswith('.fits.gz'):
                skymap_filename = fv
            if em_bright_needed \
                    and 'em_bright' in t \
                    and f.endswith('.json'):
                em_bright_filename = fv
            if p_astro_needed \
                    and 'p_astro' in t \
                    and f.endswith('.json'):
                p_astro_filename = fv

    send_canvas = (
        gracedb.download.s(superevent_id)
        |
        gcn.send.s()
    )

    if alert_type == 'preliminary':
        send_canvas |= gracedb.create_label.si(
            'GCN_PRELIM_SENT', superevent_id)

    (
        group(
            gracedb.expose.s(superevent_id),
            *(
                gracedb.create_tag.s(filename, 'public', superevent_id)
                for filename in [
                    skymap_filename, em_bright_filename, p_astro_filename
                ]
                if filename is not None
            )
        )
        |
        group(
            gracedb.download.si(em_bright_filename, superevent_id),
            gracedb.download.si(p_astro_filename, superevent_id),
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
            send_canvas,

            circulars.create_initial_circular.si(superevent_id)
            |
            gracedb.upload.s(
                '{}-circular.txt'.format(alert_type),
                superevent_id,
                'Template for {} GCN Circular'.format(alert_type),
                tags=['em_follow']
            ),

            gracedb.create_tag.s('public', superevent_id)
        )
    ).apply_async()


@gracedb.task(ignore_result=True, shared=False)
def initial_alert(filenames, superevent_id):
    """Produce an initial alert.

    This does nothing more than call
    :meth:`~gwcelery.tasks.orchestrator.preliminary_initial_update_alert` with
    ``alert_type='initial'``.

    Parameters
    ----------
    filenames : tuple
        A list of the sky map, em_bright, and p_astro filenames.
    superevent_id : str
        The superevent ID.

    Notes
    -----
    This function is decorated with :obj:`gwcelery.tasks.gracedb.task` rather
    than :obj:`gwcelery.app.task` so that a synchronous call to
    :func:`gwcelery.tasks.gracedb.get_log` is retried in the event of GraceDB
    API failures.
    """
    preliminary_initial_update_alert(filenames, superevent_id, 'initial')


@gracedb.task(ignore_result=True, shared=False)
def update_alert(filenames, superevent_id):
    """Produce an update alert.

    This does nothing more than call
    :meth:`~gwcelery.tasks.orchestrator.preliminary_initial_update_alert` with
    ``alert_type='update'``.

    Parameters
    ----------
    filenames : tuple
        A list of the sky map, em_bright, and p_astro filenames.
    superevent_id : str
        The superevent ID.

    Notes
    -----
    This function is decorated with :obj:`gwcelery.tasks.gracedb.task` rather
    than :obj:`gwcelery.app.task` so that a synchronous call to
    :func:`gwcelery.tasks.gracedb.get_log` is retried in the event of GraceDB
    API failures.
    """
    preliminary_initial_update_alert(filenames, superevent_id, 'update')


@app.task(ignore_result=True, shared=False)
def retraction_alert(superevent_id):
    """Produce a retraction alert. This is currently just a stub and does
    nothing more than create and send a VOEvent."""
    (
        gracedb.expose.si(superevent_id)
        |
        _create_voevent.si(
            None, superevent_id, 'retraction',
            internal=False,
            open_alert=True,
            vetted=True
        )
        |
        group(
            gracedb.download.s(superevent_id)
            |
            gcn.send.s(),

            circulars.create_retraction_circular.si(superevent_id)
            |
            gracedb.upload.s(
                'retraction-circular.txt',
                superevent_id,
                'Template for retraction GCN Circular',
                tags=['em_follow']
            ),

            gracedb.create_tag.s('public', superevent_id)
        )
    ).apply_async()
