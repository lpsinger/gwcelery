"""Generate and upload automated circulars."""
import ligo.followup_advocate

from . import gracedb


@gracedb.task(shared=False)
def create_circular(graceid):
    """Create and return circular txt."""
    return ligo.followup_advocate.compose(graceid, client=gracedb.client)
