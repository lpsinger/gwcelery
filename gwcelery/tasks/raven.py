"""Search for GRB-GW coincidences with ligo-raven."""
import ligo.raven.gracedb_events
import ligo.raven.search

from ..celery import app
from . import gracedb


@app.task(shared=False)
def coincidence_search(gracedb_id, alert_object):
    """Perform ligo-raven search for coincidences.
    The ligo.raven.search.search method applies EM_COINC label on its own.

    Parameters
    ----------
    gracedb_id: str
        ID of the trigger used by GraceDb
    alert_object: dict
        lvalert['object']
    Returns
    -------
        list with the dictionaries of related gracedb events
    """
    if alert_object.get('superevent_id'):
        event = ligo.raven.gracedb_events.SE(gracedb_id,
                                             gracedb=gracedb.client)
    else:
        event = ligo.raven.gracedb_events.ExtTrig(gracedb_id,
                                                  gracedb=gracedb.client)
    return (ligo.raven.search.search.s(event, -5, 5, gracedb=gracedb.client) |
            add_exttrig_to_superevent(gracedb_id))


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
