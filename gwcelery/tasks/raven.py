"""Search for GRB-GW coincidences with ligo-raven."""
import ligo.raven.search
from celery import chain, group
from ligo.gracedb.exceptions import HTTPError
from ligo.raven import gracedb_events

from ..import app
from . import gracedb
from . import ligo_fermi_skymaps


@app.task(shared=False)
def calculate_coincidence_far(superevent_id, exttrig_id, preferred_id, group):
    """Compute temporal coincidence FAR for external trigger and superevent
    coincidence by calling ligo.raven.search.calc_signif_gracedb.

    Parameters
    ----------
    gracedb_id: str
        ID of the superevent trigger used by GraceDB
    group: str
        CBC or Burst; group of the preferred_event associated with the
        gracedb_id superevent
    """
    try:
        preferred_skymap = ligo_fermi_skymaps.get_preferred_skymap(
                               preferred_id)
    except ValueError:
        preferred_skymap = None
    try:
        ext_skymap = gracedb.download('glg_healpix_all_bn_v00.fit',
                                      exttrig_id)
    except HTTPError as e:
        if e.status == 404:
            ext_skymap = None

    tl_cbc, th_cbc = app.conf['raven_coincidence_windows']['GRB_CBC']
    tl_burst, th_burst = app.conf['raven_coincidence_windows']['GRB_Burst']

    if group == 'CBC':
        tl, th = tl_cbc, th_cbc
    elif group == 'Burst':
        tl, th = tl_burst, th_burst

    canvas = chain()
    canvas |= gracedb.get_search.si(exttrig_id)
    if ext_skymap and preferred_skymap:
        canvas |= calc_signif.s(superevent_id, exttrig_id, tl, th,
                                incl_sky=True,
                                se_fitsfile=preferred_skymap)
    else:
        canvas |= calc_signif.s(superevent_id, exttrig_id, tl, th,
                                incl_sky=False)
    canvas.delay()


@app.task(shared=False)
def calc_signif(search, se_id, exttrig_id, tl, th, incl_sky=False,
                se_fitsfile=None):
    """Calculate FAR of GRB exttrig-GW coincidence"""
    return ligo.raven.search.calc_signif_gracedb(
        se_id, exttrig_id, tl, th, grb_search=search, se_fitsfile=se_fitsfile,
        incl_sky=incl_sky, gracedb=gracedb.client)


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
    elif group == 'CBC' and gracedb_id.startswith('E'):
        tl, th = tl_cbc, th_cbc
    elif group == 'CBC' and gracedb_id.startswith('S'):
        tl, th = -th_cbc, -tl_cbc
    elif group == 'Burst' and gracedb_id.startswith('E'):
        tl, th = tl_burst, th_burst
    elif group == 'Burst' and gracedb_id.startswith('S'):
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
    appropriate events.

    Parameters
    ----------
    raven_search_results: list
        list of dictionaries of each related gracedb trigger
    gracedb_id: str
        ID of either a superevent or external trigger
    alert_object: dict
        lvalert['object']
    group: str
        Burst or CBC
    """
    if not raven_search_results:
        return
    if gracedb_id.startswith('E'):
        raven_search_results = preferred_superevent(raven_search_results)
    for result in raven_search_results:
        if gracedb_id.startswith('E'):
            superevent_id = result['superevent_id']
            exttrig_id = gracedb_id
            preferred_gwevent_id = result['preferred_event']
        else:
            superevent_id = gracedb_id
            exttrig_id = result['graceid']
            preferred_gwevent_id = alert_object['preferred_event']

        (
            gracedb.add_event_to_superevent.si(superevent_id, exttrig_id)
            |
            calculate_coincidence_far.si(superevent_id, exttrig_id,
                                         preferred_gwevent_id, gw_group)
            |
            group(gracedb.create_label.si('EM_COINC', superevent_id),
                  gracedb.create_label.si('EM_COINC', exttrig_id))
        ).delay()


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
