"""Search for GRB-GW coincidences with ligo-raven."""
import ligo.raven.search
import json
from celery import group
from celery.utils.log import get_task_logger
from ligo.raven import gracedb_events

from ..import app
from . import gracedb
from . import external_skymaps

log = get_task_logger(__name__)


@app.task(shared=False)
def calculate_coincidence_far(superevent, exttrig, group):
    """Compute temporal coincidence FAR for external trigger and superevent
    coincidence by calling ligo.raven.search.calc_signif_gracedb.

    Parameters
    ----------
    superevent: dict
        superevent dictionary
    exttrig: dict
        external event dictionary
    group: str
        CBC or Burst; group of the preferred_event associated with the
        gracedb_id superevent

    """
    superevent_id = superevent['superevent_id']
    exttrig_id = exttrig['graceid']

    #  Don't compute coinc FAR for SNEWS coincidences
    if exttrig['pipeline'] == 'SNEWS':
        return

    tl_cbc, th_cbc = app.conf['raven_coincidence_windows']['GRB_CBC']
    tl_burst, th_burst = app.conf['raven_coincidence_windows']['GRB_Burst']

    if group == 'CBC':
        tl, th = tl_cbc, th_cbc
    elif group == 'Burst':
        tl, th = tl_burst, th_burst

    if {'EXT_SKYMAP_READY', 'SKYMAP_READY'}.issubset(exttrig['labels']):
        #  if both sky maps available, calculate spatial coinc far
        se_skymap = external_skymaps.get_skymap_filename(
            superevent_id)
        ext_skymap = external_skymaps.get_skymap_filename(
            exttrig_id)

        return ligo.raven.search.calc_signif_gracedb(
                   superevent_id, exttrig_id, tl, th,
                   grb_search=exttrig['search'],
                   se_fitsfile=se_skymap, ext_fitsfile=ext_skymap,
                   incl_sky=True, gracedb=gracedb.client)
    else:
        return ligo.raven.search.calc_signif_gracedb(
                   superevent_id, exttrig_id, tl, th,
                   grb_search=exttrig['search'],
                   incl_sky=False, gracedb=gracedb.client)


@app.task(shared=False)
def coincidence_search(gracedb_id, alert_object, group=None, pipelines=[]):
    """Perform ligo-raven search for coincidences.
    The ligo.raven.search.search method applies EM_COINC label on its own.

    Parameters
    ----------
    gracedb_id: str
        ID of the trigger used by GraceDB
    alert_object: dict
        lvalert['object']
    group: str
        Burst or CBC
    pipelines: list
        list of external trigger pipeline names

    """
    tl_cbc, th_cbc = app.conf['raven_coincidence_windows']['GRB_CBC']
    tl_burst, th_burst = app.conf['raven_coincidence_windows']['GRB_Burst']
    tl_snews, th_snews = app.conf['raven_coincidence_windows']['SNEWS']

    if 'SNEWS' in pipelines:
        tl, th = tl_snews, th_snews
    elif group == 'CBC' and alert_object.get('group') == 'External':
        tl, th = tl_cbc, th_cbc
    elif group == 'CBC' and 'S' in gracedb_id:
        tl, th = -th_cbc, -tl_cbc
    elif group == 'Burst' and alert_object.get('group') == 'External':
        tl, th = tl_burst, th_burst
    elif group == 'Burst' and 'S' in gracedb_id:
        tl, th = -th_burst, -tl_burst
    else:
        raise ValueError('Invalid RAVEN search request for {0}'.format(
            gracedb_id))

    (
        search.si(gracedb_id, alert_object, tl, th, group, pipelines)
        |
        raven_pipeline.s(gracedb_id, alert_object, group)
    ).delay()


@app.task(shared=False)
def search(gracedb_id, alert_object, tl=-5, th=5, group=None,
           pipelines=[]):
    """Perform ligo-raven search for coincidences.
    The ligo.raven.search.search method applies EM_COINC label on its own.

    Parameters
    ----------
    gracedb_id: str
        ID of the trigger used by GraceDB
    alert_object: dict
        lvalert['object']
    tl: int
        number of seconds to search before
    th: int
        number of seconds to search after
    group: str
        Burst or CBC
    pipelines: list
        list of external trigger pipelines for performing coincidence search
        against

    Returns
    -------
        list with the dictionaries of related gracedb events

    """
    if alert_object.get('superevent_id'):
        event = gracedb_events.SE(gracedb_id, gracedb=gracedb.client)
        group = None
    else:
        event = gracedb_events.ExtTrig(gracedb_id, gracedb=gracedb.client)
        pipelines = []
    return ligo.raven.search.search(event, tl, th, gracedb=gracedb.client,
                                    group=group, pipelines=pipelines)


@app.task(shared=False)
def raven_pipeline(raven_search_results, gracedb_id, alert_object, gw_group):
    """Executes much of the full raven pipeline, including adding
    the external trigger to the superevent, calculating the
    coincidence false alarm rate, and applying 'EM_COINC' to the
    appropriate events. Also a preimlinary alert will be triggered
    if the coincidence passes threshold.

    Parameters
    ----------
    raven_search_results: list
        list of dictionaries of each related gracedb trigger
    gracedb_id: str
        ID of either a superevent or external trigger
    alert_object: dict
        lvalert['object'], either a superevent or an external event
    gw_group: str
        Burst or CBC

    """
    if not raven_search_results:
        return
    if alert_object.get('group') == 'External':
        raven_search_results = preferred_superevent(raven_search_results)
    for result in raven_search_results:
        if alert_object.get('group') == 'External':
            superevent_id = result['superevent_id']
            exttrig_id = gracedb_id
            superevent = result
            ext_event = alert_object
        elif 'S' in gracedb_id:
            superevent_id = gracedb_id
            exttrig_id = result['graceid']
            superevent = alert_object
            ext_event = result

        canvas = (
            gracedb.add_event_to_superevent.si(superevent_id, exttrig_id)
            |
            calculate_coincidence_far.si(superevent, ext_event, gw_group)
            |
            group(gracedb.create_label.si('EM_COINC', superevent_id),
                  gracedb.create_label.si('EM_COINC', exttrig_id))
            |
            _get_coinc_far_try_raven_alert.si(superevent, ext_event,
                                              gracedb_id,
                                              superevent_id, exttrig_id,
                                              gw_group)
        )
        canvas.delay()


@app.task(shared=False)
def preferred_superevent(raven_search_results):
    """Chooses the superevent with the lowest far for an external
    event to be added to. This is to prevent errors from trying to
    add one external event to multiple superevents.

    Parameters
    ----------
    raven_search_results: list
        list of dictionaries of each related gracedb trigger

    """
    minfar, idx = min((result['far'], idx) for (idx, result) in
                      enumerate(raven_search_results))
    return [raven_search_results[idx]]


@app.task(shared=False)
def _get_coinc_far_try_raven_alert(superevent, ext_event, gracedb_id,
                                   superevent_id, exttrig_id, gw_group):
    #  FIXME: Reduce RAVEN latency to avoid this additional poll
    #  FIXME: change to return coincidence_far in ligo-raven

    if ext_event['pipeline'] != 'SNEWS':
        coinc_far_bytes = gracedb.download('coincidence_far.json',
                                           exttrig_id)
        coinc_far_dict = json.loads(coinc_far_bytes)
    else:
        coinc_far_dict = {}

    trigger_raven_alert(coinc_far_dict, superevent, gracedb_id,
                        ext_event, gw_group)


@app.task(shared=False)
def trigger_raven_alert(coinc_far_json, superevent, gracedb_id,
                        ext_event, gw_group):
    """Determine whether an event should be published as a public alert.
    If yes, then launches an alert by applying `RAVEN_ALERT` to the preferred
    event.

    All of the following conditions must be true for a public alert:

    *   The external event must be a threshold GRB or SNEWS event.
    *   If triggered on a SNEW event, the GW false alarm rate must pass
        :obj:`~gwcelery.conf.snews_gw_far_threshold`.
    *   The event's RAVEN coincidence false alarm rate, weighted by the
        group-specific trials factor as specified by the
        :obj:`~gwcelery.conf.preliminary_alert_trials_factor` configuration
        setting, is less than or equal to
        :obj:`~gwcelery.conf.preliminary_alert_far_threshold`.

    Parameters
    ----------
    coinc_far_json : dict
        Dictionary containing coincidence false alarm rate results from
        RAVEN
    superevent : dict
        superevent dictionary
    gracedb_id: str
        ID of the trigger that launched RAVEN
    ext_event: dict
        external event dictionary
    gw_group: str
        Burst or CBC

    """
    preferred_gwevent_id = superevent['preferred_event']
    superevent_id = superevent['superevent_id']
    ext_id = ext_event['graceid']
    gw_group = gw_group.lower()
    trials_factor = app.conf['preliminary_alert_trials_factor'][gw_group]

    #  Since the significance of SNEWS triggers is so high, we will publish
    #  any trigger coincident with a decently significant GW candidate
    pipeline = ext_event['pipeline']
    if 'SNEWS' == pipeline:
        gw_far = superevent['far']
        far_type = 'gw'
        far_threshold = app.conf['snews_gw_far_threshold']
        pass_far_threshold = gw_far * trials_factor < far_threshold
        is_ext_subthreshold = False
        #  Set coinc FAR to gw FAR only for the sake of a message below
        coinc_far = None
        coinc_far_f = gw_far

    #  The GBM team requested we not send automatic alerts from subthreshold
    #  GRBs. This checks that at least one threshold GRB present as well as
    #  the coinc far
    else:
        # check whether the GRB is threshold or sub-thresholds
        is_ext_subthreshold = 'SubGRB' == ext_event['search']

        # Use only temporal FAR at the moment
        coinc_far = coinc_far_json['temporal_coinc_far']

        far_type = 'joint'
        far_threshold = app.conf['preliminary_alert_far_threshold'][gw_group]
        coinc_far_f = coinc_far * trials_factor * (trials_factor - 1.)
        pass_far_threshold = coinc_far_f <= far_threshold

    no_previous_alert = {'RAVEN_ALERT'}.isdisjoint(
        gracedb.get_labels(superevent_id))

    #  If publishable, trigger an alert by applying `RAVEN_ALERT` label to
    #  preferred event
    messages = []
    if pass_far_threshold and not is_ext_subthreshold:
        messages.append('RAVEN: publishing criteria met for %s' % (
            preferred_gwevent_id))
        if no_previous_alert:
            gracedb.update_superevent(superevent_id, em_type=ext_id,
                                      coinc_far=coinc_far)
            messages.append('Triggering RAVEN alert for %s' % (
                preferred_gwevent_id))
            (
                gracedb.create_label.si('RAVEN_ALERT', superevent_id)
                |
                gracedb.create_label.si('RAVEN_ALERT', ext_id)
                |
                gracedb.create_label.si('RAVEN_ALERT', preferred_gwevent_id)
            ).delay()
    if not pass_far_threshold:
        messages.append(('RAVEN: publishing criteria not met for %s,'
                         ' %s FAR (w/ trials) too large (%s>%s)' % (
                             preferred_gwevent_id, far_type,
                             coinc_far_f, far_threshold)))
    if is_ext_subthreshold:
        messages.append(('RAVEN: publishing criteria not met for %s,'
                         ' %s is subthreshold' % (preferred_gwevent_id,
                                                  ext_id)))
    if not no_previous_alert:
        messages.append(('RAVEN: Alert already triggered for  %s'
                         % (superevent_id)))
    for message in messages:
        gracedb.upload(None, None, superevent_id,
                       message,
                       tags=['ext_coinc'])
