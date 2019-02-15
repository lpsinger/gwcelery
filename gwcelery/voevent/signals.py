"""Definitions of custom Celery signals related to VOEvents."""
from celery.utils.dispatch import Signal

voevent_received = Signal(
    name='voevent_received', providing_args=('xml_document',))
"""Sent whenever a VOEvent is received."""
