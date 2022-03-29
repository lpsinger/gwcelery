"""Definitions of custom :doc:`Celery signals <celery:userguide/signals>`
related to IGWN alerts.

These signals allow us to keep the IGWN alert broker code decoupled from any
GCN-specific logic. Notably, it allows us to keep all of the details of
the GCN-specific "Notice Type" concept out of :mod:`gwcelery.voevent`.
"""
from celery.utils.dispatch import Signal

igwn_alert_received = Signal(
    name='igwn_alert_received', providing_args=('topic', 'payload'))
"""Fired whenever a IGWN alert is received.

Parameters
----------
topic : str
    The igwn alert topic
payload : dict
    Alert dictionary
"""
