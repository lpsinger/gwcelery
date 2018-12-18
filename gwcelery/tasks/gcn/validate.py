"""Validate LIGO/Virgo GCN notices to make sure that their contents match the
original VOEvent notices that we sent."""
from urllib.parse import urlparse

import lxml.etree

from .. import gcn
from .. import gracedb


@gcn.handler(gcn.NoticeType.LVC_PRELIMINARY,
             gcn.NoticeType.LVC_INITIAL,
             gcn.NoticeType.LVC_UPDATE,
             shared=False)
def validate_voevent(payload):
    """Check that the contents of a public LIGO/Virgo GCN matches the original
    VOEvent in GraceDB."""
    if not __debug__:  # pragma: no cover
        raise RuntimeError('This task will not function correctly because '
                           'Python assertions are disabled.')

    root = lxml.etree.fromstring(payload)

    # Which GraceDB ID does this refer to?
    graceid = root.find("./What/Param[@name='GraceID']").attrib['value']

    # Skip static events from the user guide, because they are not in GraceDb.
    if graceid == 'MS181101ab':
        return

    # Which VOEvent does this refer to?
    u = urlparse(root.attrib['ivorn'])
    local_id = u.fragment
    filename = local_id + '.xml'

    # Download and parse original VOEvent
    orig = gracedb.download(filename, graceid)

    assert orig == payload, 'GCN does not match GraceDb'

    # Tag the VOEvent to indicate that it was received correctly
    gracedb.create_tag(filename, 'gcn_received', graceid)
