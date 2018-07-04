from lxml import etree
from urllib.parse import urlparse

from celery.utils.log import get_task_logger

from .. import gcn
from .. import gracedb

log = get_task_logger(__name__)


@gcn.handler(gcn.NoticeType.FERMI_GBM_ALERT,
             gcn.NoticeType.FERMI_GBM_FLT_POS,
             gcn.NoticeType.FERMI_GBM_GND_POS,
             gcn.NoticeType.FERMI_GBM_FIN_POS,
             gcn.NoticeType.SWIFT_BAT_GRB_ALERT,
             gcn.NoticeType.SWIFT_BAT_GRB_LC,
             gcn.NoticeType.SNEWS,
             queue='exttrig',
             shared=False)
def handle(payload):
    """Handles the payload from the Fermi, Swift and SNEWS alerts.
    Prepares the alert to be sent to graceDB as 'E' events."""
    root = etree.fromstring(payload)
    u = urlparse(root.attrib['ivorn'])
    stream_path = u.path

    #  Get TrigID
    trig_id = root.find("./What/Param[@name='TrigID']").attrib['value']

    stream_obsv_dict = {'/SWIFT': 'Swift',
                        '/Fermi': 'Fermi',
                        '/SNEWS': 'SNEWS'}
    event_observatory = stream_obsv_dict[stream_path]
    query = 'group: External pipeline: {} grbevent.trigger_id = "{}"'.format(
        event_observatory, trig_id)
    events = gracedb.get_events(query=query)

    if events:
        assert len(events) == 1, 'Found more than one matching GraceDb entry'
        event, = events
        graceid = event['graceid']
        gracedb.replace_event(graceid, payload)

    else:
        gracedb.create_event(filecontents=payload,
                             search='GRB',
                             group='External',
                             pipeline=event_observatory)
