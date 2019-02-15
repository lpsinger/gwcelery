"""Tasks for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
from urllib.parse import urlparse

from comet.utility.xml import xml_document
import gcn
from gcn import get_notice_type, NoticeType
import lxml.etree
from twisted.internet import reactor

from ..voevent.signals import voevent_received
from ..import app
from .core import DispatchHandler
from . import gracedb


class _VOEventDispatchHandler(DispatchHandler):

    def process_args(self, event):
        notice_type = get_notice_type(event.element)

        # Just cast to enum for prettier log messages
        try:
            notice_type = NoticeType(notice_type)
        except ValueError:
            pass

        return notice_type, (event.raw_bytes,), {}


handler = _VOEventDispatchHandler()
r"""Function decorator to register a handler callback for specified GCN notice
types. The decorated function is turned into a Celery task, which will be
automatically called whenever a matching GCN notice is received.

Parameters
----------
\*keys
    List of GCN notice types to accept
\*\*kwargs
    Additional keyword arguments for :meth:`celery.Celery.task`.

Examples
--------
Declare a new handler like this::

    @gcn.handler(gcn.NoticeType.FERMI_GBM_GND_POS,
                 gcn.NoticeType.FERMI_GBM_FIN_POS)
    def handle_fermi(payload):
        root = lxml.etree.fromstring(payload)
        # do work here...
"""


@voevent_received.connect
def _on_voevent_received(xml_document, **kwargs):
    handler.dispatch(xml_document)


class SendingError(RuntimeError):
    """A generic error associated with sending VOEvents."""


@app.task(autoretry_for=(SendingError,), bind=True, default_retry_delay=20.0,
          ignore_result=True, queue='voevent', retry_backoff=True,
          retry_kwargs=dict(max_retries=10), shared=False)
def send(self, message):
    broadcasters = self.app.conf['voevent_broadcaster_factory'].broadcasters
    if not broadcasters:
        raise SendingError('Not sending the event because there are no '
                           'subscribers connected to the GCN broker.')
    event = xml_document(message)
    for broadcaster in broadcasters:
        reactor.callFromThread(broadcaster.send_event, event)


@handler(gcn.NoticeType.LVC_PRELIMINARY,
         gcn.NoticeType.LVC_INITIAL,
         gcn.NoticeType.LVC_UPDATE,
         gcn.NoticeType.LVC_RETRACTION,
         shared=False)
def validate(payload):
    """Check that the contents of a public LIGO/Virgo GCN matches the original
    VOEvent in GraceDB."""
    if not __debug__:  # pragma: no cover
        raise RuntimeError('This task will not function correctly because '
                           'Python assertions are disabled.')

    root = lxml.etree.fromstring(payload)

    # Which GraceDB ID does this refer to?
    graceid = root.find("./What/Param[@name='GraceID']").attrib['value']

    # Which VOEvent does this refer to?
    u = urlparse(root.attrib['ivorn'])
    local_id = u.fragment
    filename = local_id + '.xml'

    # Download and parse original VOEvent
    orig = gracedb.download(filename, graceid)

    assert orig == payload, 'GCN does not match GraceDb'

    # Tag the VOEvent to indicate that it was received correctly
    gracedb.create_tag(filename, 'gcn_received', graceid)
