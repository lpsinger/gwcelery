"""Tasks for sending, receiving, and processing Gamma-ray Coordinates
Network [GCN]_ notices.

References
----------

.. [GCN] https://gcn.gsfc.nasa.gov
"""
import html
import difflib
import urllib.parse

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
    """Send a VOEvent to GCN.

    This task will be retried several times if the VOEvent cannot be sent. See
    the Raises section below for circumstances that cause a retry.

    Parameters
    ----------
    message : bytes
        The raw VOEvent file contents.

    Raises
    ------
    SendingError
        If the VOEvent could not be sent because there were no network peers
        connected to the VOEvent broadcaster.
    """
    broadcasters = self.app.conf['voevent_broadcaster_factory'].broadcasters
    if broadcasters:
        event = xml_document(message)
        for broadcaster in broadcasters:
            reactor.callFromThread(broadcaster.send_event, event)
    elif self.app.conf['voevent_broadcaster_whitelist']:
        raise SendingError('Not sending the event because there are no '
                           'subscribers connected to the GCN broker.')


@handler(gcn.NoticeType.LVC_PRELIMINARY,
         gcn.NoticeType.LVC_INITIAL,
         gcn.NoticeType.LVC_UPDATE,
         gcn.NoticeType.LVC_RETRACTION,
         bind=True, shared=False)
def validate(self, payload):
    """Check that the contents of a public LIGO/Virgo GCN matches the original
    VOEvent in GraceDB.

    Notes
    -----
    If the VOEvent broadcaster is disabled by setting
    :obj:`~gwcelery.conf.voevent_broadcaster_whitelist` to an empty list, then
    this task becomes a no-op."""

    if not self.app.conf['voevent_broadcaster_whitelist']:
        return

    root = lxml.etree.fromstring(payload)

    # Which GraceDB ID does this refer to?
    graceid = root.find("./What/Param[@name='GraceID']").attrib['value']

    # Which VOEvent does this refer to?
    u = urllib.parse.urlparse(root.attrib['ivorn'])
    local_id = u.fragment
    filename = local_id + '.xml'

    # Download and parse original VOEvent
    orig = gracedb.download(filename, graceid)

    # Create a diff of the two VOEvents.
    diff = ''.join(
        difflib.unified_diff(
            *(
                [
                    line.decode('ascii', 'surrogateescape')
                    for line in contents.splitlines(keepends=True)
                ]
                for contents in (orig, payload)
            ),
            fromfile='{} (sent)'.format(filename),
            tofile='{} (received)'.format(filename)
        )
    )

    if diff:
        # Write a log message to indicate that the event differed.
        msg = 'VOEvent received from GCN differs from what we sent.'
        gracedb.upload.delay(
            None, None, graceid,
            '{}<pre>{}</pre>'.format(msg, html.escape(diff)),
            ['em_follow'])
        raise ValueError('{}\n\n{}'.format(msg, diff))
    else:
        # Tag the VOEvent to indicate that it was received correctly.
        gracedb.create_tag.delay(filename, 'gcn_received', graceid)
