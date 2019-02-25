"""Definitions of custom :doc:`Celery signals <celery:userguide/signals>`
related to VOEvents.

These signals allow us to keep the VOEvent broker code decoupled from any
GCN-specific logic. Notably, it allows us to keep all of the details of
the GCN-specific "Notice Type" concept out of :mod:`gwcelery.voevent`.
"""
from celery.utils.dispatch import Signal

voevent_received = Signal(
    name='voevent_received', providing_args=('xml_document',))
"""Fired whenever a VOEvent is received.

Parameters
----------
xml_document : :class:`comet.utility.xml.xml_document`
    The XML document that was received. The raw file contents are available as
    ``xml_document.raw_bytes``. The ``lxml.etree`` representation of the
    document is available as ``xml_document.element``.
"""
