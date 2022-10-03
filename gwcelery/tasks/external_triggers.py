from lxml import etree
from urllib.parse import urlparse
from celery import group
from celery.utils.log import get_logger

from ..import app
from . import detchar
from . import gcn
from . import gracedb
from . import external_skymaps
from . import igwn_alert
from . import raven

log = get_logger(__name__)


REQUIRED_LABELS_BY_TASK = {
    'compare': {'SKYMAP_READY', 'EXT_SKYMAP_READY', 'EM_COINC'},
    'combine': {'SKYMAP_READY', 'EXT_SKYMAP_READY', 'RAVEN_ALERT'}
}
"""These labels should be present on an external event to consider it to
be ready for sky map comparison.
"""

FERMI_GRB_CLASS_VALUE = 4
"""This is the index that denote GRBs within Fermi's Flight Position
classification."""

FERMI_GRB_CLASS_THRESH = 50
"""This values denotes the threshold of the most likely Fermi source
classification, above which we will consider a Fermi Flight Position
notice."""


@gcn.handler(gcn.NoticeType.SNEWS,
             queue='exttrig',
             shared=False)
def handle_snews_gcn(payload):
    """Handles the payload from SNEWS alerts.

    Prepares the alert to be sent to graceDB as 'E' events.
    """
    root = etree.fromstring(payload)

    #  Get TrigID and Test Event Boolean
    trig_id = root.find("./What/Param[@name='TrigID']").attrib['value']
    ext_group = 'Test' if root.attrib['role'] == 'test' else 'External'

    event_observatory = 'SNEWS'
    query = 'group: External pipeline: {} grbevent.trigger_id = "{}"'.format(
        event_observatory, trig_id)
    events = gracedb.get_events(query=query)

    if events:
        assert len(events) == 1, 'Found more than one matching GraceDB entry'
        event, = events
        graceid = event['graceid']
        gracedb.replace_event(graceid, payload)
        return

    else:
        graceid = gracedb.create_event(filecontents=payload,
                                       search='Supernova',
                                       group=ext_group,
                                       pipeline=event_observatory)
    event = gracedb.get_event(graceid)
    start, end = event['gpstime'], event['gpstime']
    # Pre-start and post-end padding is applied by check_vectors
    detchar.check_vectors(event, event['graceid'], start, end)


@gcn.handler(gcn.NoticeType.FERMI_GBM_ALERT,
             gcn.NoticeType.FERMI_GBM_FLT_POS,
             gcn.NoticeType.FERMI_GBM_GND_POS,
             gcn.NoticeType.FERMI_GBM_FIN_POS,
             gcn.NoticeType.SWIFT_BAT_GRB_POS_ACK,
             gcn.NoticeType.FERMI_GBM_SUBTHRESH,
             gcn.NoticeType.INTEGRAL_WAKEUP,
             gcn.NoticeType.INTEGRAL_REFINED,
             gcn.NoticeType.INTEGRAL_OFFLINE,
             gcn.NoticeType.AGILE_MCAL_ALERT,
             queue='exttrig',
             shared=False)
def handle_grb_gcn(payload):
    """Handles the payload from Fermi, Swift, INTEGRAL, and AGILE MCAL
    GCN notices.

    Filters out candidates likely to be noise. Creates external events
    from the notice if new notice, otherwise updates existing event. Then
    creates and/or grabs external sky map to be uploaded to the external event.

    More info for these notices can be found at:
    Fermi-GBM: https://gcn.gsfc.nasa.gov/fermi_grbs.html
    Fermi-GBM sub: https://gcn.gsfc.nasa.gov/fermi_gbm_subthresh_archive.html
    Swift: https://gcn.gsfc.nasa.gov/swift.html
    INTEGRAL: https://gcn.gsfc.nasa.gov/integral.html
    AGILE-MCAL: https://gcn.gsfc.nasa.gov/agile_mcal.html
    """
    root = etree.fromstring(payload)
    u = urlparse(root.attrib['ivorn'])
    stream_path = u.path

    #  Get TrigID
    try:
        trig_id = root.find("./What/Param[@name='TrigID']").attrib['value']
    except AttributeError:
        trig_id = root.find("./What/Param[@name='Trans_Num']").attrib['value']
    ext_group = 'Test' if root.attrib['role'] == 'test' else 'External'

    notice_type = \
        int(root.find("./What/Param[@name='Packet_Type']").attrib['value'])

    stream_obsv_dict = {'/SWIFT': 'Swift',
                        '/Fermi': 'Fermi',
                        '/INTEGRAL': 'INTEGRAL',
                        '/AGILE': 'AGILE'}
    event_observatory = stream_obsv_dict[stream_path]

    reliability = root.find("./What/Param[@name='Reliability']")
    if reliability is not None and int(reliability.attrib['value']) <= 4:
        return

    #  Check if Fermi trigger is likely noise by checking classification
    #  Most_Likely_Index of 4 is an astrophysical GRB
    #  If not at least 50% chance of GRB we will not consider it for RAVEN
    likely_source = root.find("./What/Param[@name='Most_Likely_Index']")
    likely_prob = root.find("./What/Param[@name='Most_Likely_Prob']")
    not_likely_grb = likely_source is not None and \
        (likely_source.attrib['value'] != FERMI_GRB_CLASS_VALUE
         or likely_prob.attrib['value'] < FERMI_GRB_CLASS_THRESH)

    #  Check if initial Fermi alert. These are generally unreliable and should
    #  never trigger a RAVEN alert, but will give us earlier warning of a
    #  possible coincidence. Later notices could change this.
    initial_gbm_alert = notice_type == gcn.NoticeType.FERMI_GBM_ALERT

    #  Check if Swift has lost lock. If so then veto
    lost_lock = \
        root.find("./What/Group[@name='Solution_Status']" +
                  "/Param[@name='StarTrack_Lost_Lock']")
    swift_veto = lost_lock is not None and lost_lock.attrib['value'] == 'true'

    #  Only send alerts if likely a GRB, is not a low-confidence early Fermi
    #  alert, and if not a Swift veto
    if not_likely_grb or initial_gbm_alert or swift_veto:
        labels = ['NOT_GRB']
    else:
        labels = None

    ivorn = root.attrib['ivorn']
    if 'subthresh' in ivorn.lower():
        search = 'SubGRB'
    elif 'mdc-test_event' in ivorn.lower():
        search = 'MDC'
    else:
        search = 'GRB'

    query = 'group: External pipeline: {} grbevent.trigger_id = "{}"'.format(
        event_observatory, trig_id)
    events = gracedb.get_events(query=query)

    group_canvas = ()
    if events:
        assert len(events) == 1, 'Found more than one matching GraceDB entry'
        event, = events
        graceid = event['graceid']
        if labels:
            canvas = gracedb.create_label.si(labels[0], graceid)
        else:
            canvas = gracedb.remove_label.si('NOT_GRB', graceid)

        # Prevent SubGRBs from appending GRBs
        if search == 'GRB':
            canvas |= gracedb.replace_event.si(graceid, payload)
        else:
            return

    else:
        canvas = gracedb.create_event.s(filecontents=payload,
                                        search=search,
                                        group=ext_group,
                                        pipeline=event_observatory,
                                        labels=labels)
        group_canvas += _launch_external_detchar.s(),

    if search in {'GRB', 'MDC'}:
        notice_date = root.find("./Who/Date").text
        group_canvas += external_skymaps.create_upload_external_skymap.s(
                      notice_type, notice_date),
    if event_observatory == 'Fermi':
        if search == 'SubGRB':
            skymap_link = \
                root.find("./What/Param[@name='HealPix_URL']").attrib['value']
            group_canvas += \
                external_skymaps.get_upload_external_skymap.s(skymap_link),
        elif search == 'GRB':
            skymap_link = None
            group_canvas += \
                external_skymaps.get_upload_external_skymap.s(skymap_link),

    (
        canvas
        |
        group(group_canvas)
    ).delay()


@igwn_alert.handler('superevent',
                    'mdc_superevent',
                    'external_fermi',
                    'external_swift',
                    'external_integral',
                    'external_agile',
                    shared=False)
def handle_grb_igwn_alert(alert):
    """Parse an IGWN alert message related to superevents/GRB external triggers
    and dispatch it to other tasks.

    Notes
    -----
    This IGWN alert message handler is triggered by creating a new superevent
    or GRB external trigger event, or a label associated with completeness of
    skymaps:

    * Any new event triggers a coincidence search with
      :meth:`gwcelery.tasks.raven.coincidence_search`.
    * When both a GW and GRB sky map are available during a coincidence,
      indicated by the labels ``SKYMAP_READY`` and ``EXT_SKYMAP_READY``
      respectively on the external event, this triggers the spacetime coinc
      FAR to be calculated. If an alert is triggered with these same
      conditions, indicated by the ``RAVEN_ALERT`` label, a combined GW-GRB
      sky map is created using
      :meth:`gwcelery.tasks.external_skymaps.create_combined_skymap`.

    """
    # Determine GraceDB ID
    graceid = alert['uid']

    # launch searches
    if alert['alert_type'] == 'new':
        if alert['object'].get('group') == 'External':
            # Create and upload Swift sky map for the joint targeted
            # sub-threshold search as agreed on in the MOU
            if alert['object']['search'] == 'SubGRBTargeted' and \
                    alert['object']['pipeline'] == 'Swift':
                external_skymaps.create_upload_external_skymap(
                    alert['object'], None, alert['object']['created'])

            # launch search with MDC events and exit
            if alert['object']['search'] == 'MDC':
                raven.coincidence_search(graceid, alert['object'],
                                         group='CBC', se_searches=['MDC'])
                raven.coincidence_search(graceid, alert['object'],
                                         group='Burst', se_searches=['MDC'])
                return

            # launch standard Burst-GRB search
            raven.coincidence_search(graceid, alert['object'], group='Burst',
                                     se_searches=['Allsky'])

            if alert['object']['search'] in ['SubGRB', 'SubGRBTargeted']:
                # if sub-threshold GRB, launch search with that pipeline
                raven.coincidence_search(
                    graceid, alert['object'], group='CBC',
                    searches=['SubGRB', 'SubGRBTargeted'],
                    pipelines=[alert['object']['pipeline']])
            else:
                # if threshold GRB, launch standard CBC-GRB search
                raven.coincidence_search(graceid, alert['object'],
                                         group='CBC', searches=['GRB'])
        elif 'S' in graceid:
            # launch standard GRB search based on group
            gw_group = alert['object']['preferred_event_data']['group']

            # launch search with MDC events and exit
            if alert['object']['preferred_event_data']['search'] == 'MDC':
                raven.coincidence_search(graceid, alert['object'],
                                         group=gw_group, searches=['MDC'])
                return

            if gw_group == 'CBC':
                # launch subthreshold searches if CBC
                # for Fermi and Swift separately to use different time windows
                for pipeline in ['Fermi', 'Swift']:
                    raven.coincidence_search(
                        graceid, alert['object'], group='CBC',
                        searches=['SubGRB', 'SubGRBTargeted'],
                        pipelines=[pipeline])
                se_searches = []
            else:
                se_searches = ['Allsky']
            # launch standard GRB search
            raven.coincidence_search(graceid, alert['object'],
                                     group=gw_group, searches=['GRB'],
                                     se_searches=se_searches)
    # rerun raven pipeline or created combined sky map when sky maps are
    # available
    elif alert['alert_type'] == 'label_added' and \
            alert['object'].get('group') == 'External':
        if _skymaps_are_ready(alert['object'], alert['data']['name'],
                              'compare'):
            # if both sky maps present and a coincidence, compare sky maps
            superevent_id, ext_ids = _get_superevent_ext_ids(
                graceid, alert['object'], 'compare')
            superevent = gracedb.get_superevent(superevent_id)
            preferred_event_id = superevent['preferred_event']
            gw_group = gracedb.get_group(preferred_event_id)
            tl, th = raven._time_window(graceid, gw_group,
                                        [alert['object']['pipeline']],
                                        [alert['object']['search']])
            raven.raven_pipeline([alert['object']], superevent_id, superevent,
                                 tl, th, gw_group)
        if _skymaps_are_ready(alert['object'], alert['data']['name'],
                              'combine'):
            # if both sky maps present and a raven alert, create combined
            # skymap
            superevent_id, ext_id = _get_superevent_ext_ids(
                graceid, alert['object'], 'combine')
            external_skymaps.create_combined_skymap(superevent_id, ext_id)
        elif 'EM_COINC' in alert['object']['labels']:
            # if not complete, check if GW sky map; apply label to external
            # event if GW sky map
            se_labels = gracedb.get_labels(alert['object']['superevent'])
            if 'SKYMAP_READY' in se_labels:
                gracedb.create_label.si('SKYMAP_READY', graceid).delay()
    elif alert['alert_type'] == 'label_added' and 'S' in graceid and \
            'SKYMAP_READY' in alert['object']['labels']:
        # if sky map in superevent, apply label to all external events
        # at the time
        group(
            gracedb.create_label.si('SKYMAP_READY', ext_id)
            for ext_id in alert['object']['em_events']
        ).delay()
    elif alert['alert_type'] == 'label_removed' and \
            alert['object'].get('group') == 'External':
        if alert['data']['name'] == 'NOT_GRB':
            # if NOT_GRB is removed, re-check publishing conditions
            superevent_id = alert['object']['superevent']
            superevent = gracedb.get_superevent(superevent_id)
            gw_group = superevent['preferred_event_data']['group']
            coinc_far_dict = {
                'temporal_coinc_far': superevent['time_coinc_far'],
                'spatiotemporal_coinc_far': superevent['space_coinc_far']
            }
            raven.trigger_raven_alert(coinc_far_dict, superevent, graceid,
                                      alert['object'], gw_group)


@igwn_alert.handler('superevent',
                    'mdc_superevent',
                    'external_snews',
                    shared=False)
def handle_snews_igwn_alert(alert):
    """Parse an IGWN alert message related to superevents/SN external triggers
    and dispatch it to other tasks.

    Notes
    -----
    This igwn_alert message handler is triggered by creating a new superevent
    or SN external trigger event:

    * Any new event triggers a coincidence search with
      :meth:`gwcelery.tasks.raven.coincidence_search`.

    """
    # Determine GraceDB ID
    graceid = alert['uid']

    if alert['alert_type'] == 'new':
        if alert['object'].get('superevent_id'):
            group = alert['object']['preferred_event_data']['group']
            # Run on Test and Burst superevents
            if group in {'Burst', 'Test'}:
                raven.coincidence_search(graceid, alert['object'],
                                         group='Burst', searches=['Supernova'],
                                         pipelines=['SNEWS'])
        else:
            # Run on SNEWS event, either real or test
            raven.coincidence_search(graceid, alert['object'],
                                     group='Burst', searches=['Supernova'],
                                     pipelines=['SNEWS'])


def _skymaps_are_ready(event, label, task):
    label_set = set(event['labels'])
    required_labels = REQUIRED_LABELS_BY_TASK[task]
    return required_labels.issubset(label_set) and label in required_labels


def _get_superevent_ext_ids(graceid, event, task):
    if task == 'combine':
        if 'S' in graceid:
            se_id = event['superevent_id']
            ext_id = event['em_type']
        else:
            se_id = event['superevent']
            ext_id = event['graceid']
    elif task == 'compare':
        if 'S' in graceid:
            se_id = event['superevent_id']
            ext_id = event['em_events']
        else:
            se_id = event['superevent']
            ext_id = [event['graceid']]
    return se_id, ext_id


@app.task(shared=False)
def _launch_external_detchar(event):
    start = event['gpstime']
    if event['search'] == 'Supernova':
        start, end = event['gpstime'], event['gpstime']
    else:
        integration_time = \
            event['extra_attributes']['GRB']['trigger_duration'] or 4.0
        end = start + integration_time
    detchar.check_vectors.si(event, event['graceid'], start, end).delay()

    return event
