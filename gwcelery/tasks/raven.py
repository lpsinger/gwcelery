"""Search for GRB-GW coincidences with ligo-raven."""
import ligo.raven.search
from celery import chain
from ligo.raven import gracedb_events

from ..import app
from . import gracedb
from . import ligo_fermi_skymaps


tl_cbc, th_cbc = -5, 1
tl_burst, th_burst = -600, 60


def calculate_spacetime_coincidence_far(gracedb_id, group):
    """Compute spatio-temporal coincidence FAR for GRB external trigger and
    superevent coincidence by calling ligo.raven.search.calc_signif_gracedb.
    Note: this will only run if skymaps from both triggers are available to
    download.

    Parameters
    ----------
    gracedb_id: str
        ID of the superevent trigger used by GraceDb
    group: str
        CBC or Burst; group of the preferred_event associated with the
        gracedb_id superevent
    """
    preferred_skymap = ligo_fermi_skymaps.get_preferred_skymap(gracedb_id)
    se = gracedb_events.SE(gracedb_id, fitsfile=preferred_skymap,
                           gracedb=gracedb.client)
    em_events = gracedb.get_superevent(gracedb_id)['em_events']

    if group == 'CBC':
        tl, th = tl_cbc, th_cbc
    elif group == 'Burst':
        tl, th = tl_burst, th_burst

    canvas = chain()
    for exttrig_id in em_events:
        if gracedb.download('glg_healpix_all_bn_v00.fit', exttrig_id):
            exttrig = gracedb_events.ExtTrig(exttrig_id,
                                             gracedb=gracedb.client)
            canvas |= (
                calc_signif.si(se, exttrig, tl, th, incl_sky=True))

    return canvas


def calculate_coincidence_far(gracedb_id, group):
    """Compute temporal coincidence FAR for external trigger and superevent
    coincidence by calling ligo.raven.search.calc_signif_gracedb.

    Parameters
    ----------
    gracedb_id: str
        ID of the superevent trigger used by GraceDb
    group: str
        CBC or Burst; group of the preferred_event associated with the
        gracedb_id superevent
    """
    se = gracedb_events.SE(gracedb_id, gracedb=gracedb.client)
    em_events = gracedb.get_superevent(gracedb_id)['em_events']

    if group == 'CBC':
        tl, th = tl_cbc, th_cbc
    elif group == 'Burst':
        tl, th = tl_burst, th_burst

    canvas = chain()
    for exttrig_id in em_events:
        if gracedb.get_event(exttrig_id)['search'] == 'GRB':
            exttrig = gracedb_events.ExtTrig(exttrig_id,
                                             gracedb=gracedb.client)
            canvas |= (
                calc_signif.si(se, exttrig, tl, th, incl_sky=False))

    return canvas


@app.task(shared=False)
def calc_signif(se, exttrig, tl, th, incl_sky):
    """Calculate FAR of GRB exttrig-GW coincidence"""
    return ligo.raven.search.calc_signif_gracedb(se, exttrig, tl, th,
                                                 incl_sky=incl_sky)


def coincidence_search(gracedb_id, alert_object, group=None, pipelines=[]):
    """Perform ligo-raven search for coincidences.
    The ligo.raven.search.search method applies EM_COINC label on its own.

    Parameters
    ----------
    gracedb_id: str
        ID of the trigger used by GraceDb
    alert_object: dict
        lvalert['object']
    group: str
        Burst or CBC
    pipelines: list
        list of external trigger pipeline names
    """
    if 'SNEWS' in pipelines:
        tl, th = -10, 10
    if group == 'CBC' and gracedb_id.startswith('E'):
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
    return (
        search.s(gracedb_id, alert_object, tl, th, group=group,
                 pipelines=pipelines)
        |
        add_exttrig_to_superevent.s(gracedb_id)
    )


@app.task(shared=False)
def search(gracedb_id, alert_object, tl=-5, th=5, group=None,
           pipelines=[]):
    """Perform ligo-raven search for coincidences.
    The ligo.raven.search.search method applies EM_COINC label on its own.

    Parameters
    ----------
    gracedb_id: str
        ID of the trigger used by GraceDb
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
def add_exttrig_to_superevent(raven_search_results, gracedb_id):
    """Add external trigger to the list of em_events after
    ligo.raven.search.search finds a coincidence

    Parameters
    ----------
    raven_search_results: list
        list of dictionaries of each related gracedb trigger
    gracedb_id: str
        ID of either a superevent or external trigger
    """
    # First determine whether the gracedb_id is for a superevent or exttrig
    if gracedb_id.startswith('E'):
        for superevent in raven_search_results:
            superevent_id = superevent['superevent_id']
            gracedb.client.addEventToSuperevent(superevent_id, gracedb_id)
    else:
        for exttrig in raven_search_results:
            exttrig_id = exttrig['graceid']
            gracedb.client.addEventToSuperevent(gracedb_id, exttrig_id)
