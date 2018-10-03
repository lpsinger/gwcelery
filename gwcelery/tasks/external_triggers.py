from lxml import etree
from urllib.parse import urlparse

from celery.utils.log import get_task_logger

from . import detchar
from . import gcn
from . import gracedb
from . import ligo_fermi_skymaps
from . import lvalert
from . import raven

log = get_task_logger(__name__)


@gcn.handler(gcn.NoticeType.SNEWS,
             queue='exttrig',
             shared=False)
def handle_sn_gcn(payload):
    """Handles the payload from SNEWS alerts.
    Prepares the alert to be sent to graceDB as 'E' events."""
    root = etree.fromstring(payload)

    #  Get TrigID
    trig_id = root.find("./What/Param[@name='TrigID']").attrib['value']

    event_observatory = 'SNEWS'
    query = 'group: External pipeline: {} grbevent.trigger_id = "{}"'.format(
        event_observatory, trig_id)
    events = gracedb.get_events(query=query)

    if events:
        assert len(events) == 1, 'Found more than one matching GraceDb entry'
        event, = events
        graceid = event['graceid']
        gracedb.replace_event(graceid, payload)

    else:
        graceid = gracedb.create_event(filecontents=payload,
                                       search='Supernova',
                                       group='External',
                                       pipeline=event_observatory)
        event = gracedb.get_event(graceid)
        start = event['gpstime'] - 10
        end = start + 10
        detchar.check_vectors(event, event['graceid'], start, end)


@gcn.handler(gcn.NoticeType.FERMI_GBM_ALERT,
             gcn.NoticeType.FERMI_GBM_FLT_POS,
             gcn.NoticeType.FERMI_GBM_GND_POS,
             gcn.NoticeType.FERMI_GBM_FIN_POS,
             gcn.NoticeType.SWIFT_BAT_GRB_ALERT,
             gcn.NoticeType.SWIFT_BAT_GRB_LC,
             queue='exttrig',
             shared=False)
def handle_grb_gcn(payload):
    """Handles the payload from Fermi and Swift alerts.
    Prepares the alert to be sent to graceDB as 'E' events."""
    root = etree.fromstring(payload)
    u = urlparse(root.attrib['ivorn'])
    stream_path = u.path

    #  Get TrigID
    trig_id = root.find("./What/Param[@name='TrigID']").attrib['value']

    stream_obsv_dict = {'/SWIFT': 'Swift',
                        '/Fermi': 'Fermi'}
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
        graceid = gracedb.create_event(filecontents=payload,
                                       search='GRB',
                                       group='External',
                                       pipeline=event_observatory)
        event = gracedb.get_event(graceid)
        start = event['gpstime']
        end = start + event['extra_attributes']['GRB']['trigger_duration']
        detchar.check_vectors(event, event['graceid'], start, end)


@lvalert.handler('superevent',
                 'mdc_superevent',
                 'test_superevent',
                 'external_fermi',
                 'external_fermi_grb',
                 'external_grb',
                 'external_swift',
                 shared=False)
def handle_grb_lvalert(alert):
    """Parse an LVAlert message related to superevents/GRB external triggers
    and dispatch it to other tasks.

    Notes
    -----

    This LVAlert message handler is triggered by creating a new superevent or
    GRB external trigger event, or applying the ``EM_COINC`` label to any
    superevent:

    * Any new event triggers a coincidence search with
      :meth:`gwcelery.tasks.raven.coincidence_search`.
    * The ``EM_COINC`` label triggers the creation of a combined GW-GRB sky map
      using :meth:`gwcelery.tasks.ligo_fermi_skymaps.create_combined_skymap`.
    """
    # Determine GraceDb ID
    graceid = alert['uid']

    if alert['alert_type'] == 'new' and \
            alert['object'].get('group', '') == 'External':
        raven.coincidence_search(graceid, alert['object'], group='CBC').delay()
        raven.coincidence_search(graceid, alert['object'],
                                 group='Burst').delay()
    elif graceid.startswith('S'):
        preferred_event_id = gracedb.get_superevent(graceid)['preferred_event']
        group = gracedb.get_event(preferred_event_id)['group']
        if alert['alert_type'] == 'new':
            raven.coincidence_search(graceid, alert['object'],
                                     group=group,
                                     pipelines=['Fermi', 'Swift']).delay()
        elif alert['alert_type'] == 'label_added':
            if alert['data']['name'] == 'EM_COINC':
                ligo_fermi_skymaps.create_combined_skymap(graceid).delay()
                raven.calculate_coincidence_far(graceid, group).delay()
                raven.calculate_spacetime_coincidence_far(graceid,
                                                          group).delay()


@lvalert.handler('superevent',
                 'mdc_superevent',
                 'test_superevent',
                 'external_snews',
                 'external_snews_supernova',
                 shared=False)
def handle_sn_lvalert(alert):
    """Parse an LVAlert message related to superevents/SN external triggers and
    dispatch it to other tasks.

    Notes
    -----

    This LVAlert message handler is triggered by creating a new superevent or
    SN external trigger event, or applying the ``EM_COINC`` label to any
    superevent:

    * Any new event triggers a coincidence search with
      :meth:`gwcelery.tasks.raven.coincidence_search`.
    """
    # Determine GraceDb ID
    graceid = alert['uid']

    if alert['alert_type'] == 'new' and \
            alert['object'].get('group', '') == 'External':
        raven.coincidence_search(graceid, alert['object'],
                                 group='Burst', pipelines=['SNEWS']).delay()
    elif graceid.startswith('S'):
        preferred_event_id = gracedb.get_superevent(graceid)['preferred_event']
        group = gracedb.get_event(preferred_event_id)['group']
        if alert['alert_type'] == 'new':
            raven.coincidence_search(graceid, alert['object'],
                                     group=group, pipelines=['SNEWS']).delay()
