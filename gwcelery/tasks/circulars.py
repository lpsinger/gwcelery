"""Generate and upload automated circulars."""
import ligo.followup_advocate

from . import legacy_gracedb as gracedb


@gracedb.task(shared=False)
def create_initial_circular(graceid):
    """Create and return circular txt."""
    return ligo.followup_advocate.compose(graceid, client=gracedb.client)


@gracedb.task(shared=False)
def create_emcoinc_circular(graceid):
    """Create and return the em_coinc circular txt."""
    return ligo.followup_advocate.compose_raven(graceid,
                                                client=gracedb.client)


@gracedb.task(shared=False)
def create_update_circular(graceid, update_types=['sky_localization',
                                                  'em_bright',
                                                  'p_astro']):
    """Create and return update circular txt."""
    return ligo.followup_advocate.compose_update(graceid,
                                                 update_types=update_types,
                                                 client=gracedb.client)


@gracedb.task(shared=False)
def create_retraction_circular(graceid):
    """Create and return retraction circular txt."""
    return ligo.followup_advocate.compose_retraction(graceid,
                                                     client=gracedb.client)
