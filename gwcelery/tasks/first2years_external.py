"""Create mock external events to be in coincidence
   with MDC superevents."""

from astropy.time import Time
from lxml import etree
import numpy as np
from pathlib import Path
import random
import re

from ..import app
from . import external_triggers
from . import igwn_alert


def create_grb_event(gpstime, pipeline):

    new_date = str(Time(gpstime, format='gps', scale='utc').isot)
    new_TrigID = str(int(gpstime))

    fname = str(Path(__file__).parent /
                '../tests/data/{}_grb_gcn.xml'.format(pipeline.lower()))

    root = etree.parse(fname)

    # Change ivorn to indicate is an MDC event
    root.xpath('.')[0].attrib['ivorn'] = \
        'ivo://lvk.internal/{0}#MDC-test_event{1}'.format(
            pipeline if pipeline != 'Swift' else 'SWIFT', new_date).encode()

    # Change times to chosen time
    root.find("./Who/Date").text = str(new_date).encode()
    root.find(("./WhereWhen/ObsDataLocation/"
               "ObservationLocation/AstroCoords/Time/TimeInstant/"
               "ISOTime")).text = str(new_date).encode()
    root.find("./What/Param[@name='TrigID']").attrib['value'] = \
        str(new_TrigID).encode()

    # Give random sky position
    root.find(("./WhereWhen/ObsDataLocation/"
               "ObservationLocation/AstroCoords/Position2D/Value2/"
               "C1")).text = str(random.uniform(0, 360)).encode()
    thetas = np.arange(-np.pi / 2, np.pi / 2, .01)
    root.find(("./WhereWhen/ObsDataLocation/"
               "ObservationLocation/AstroCoords/Position2D/Value2/"
               "C2")).text = \
        str(random.choices(
            np.rad2deg(thetas),
            weights=np.cos(thetas) / sum(np.cos(thetas)))[0]).encode()
    if pipeline != 'Swift':
        root.find(("./WhereWhen/ObsDataLocation/"
                   "ObservationLocation/AstroCoords/Position2D/"
                   "Error2Radius")).text = str(random.uniform(1, 30)).encode()

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          pretty_print=True)


def _offset_time(gpstime):
    # Reverse when searching around superevents
    th_cbc, tl_cbc = app.conf['raven_coincidence_windows']['GRB_CBC']
    return gpstime + random.uniform(-tl_cbc, -th_cbc)


def _is_joint_mdc(graceid):
    """Upload external event to every ten MDCs

    Looks at the ending letters of a superevent (e.g. 'ac' from 'MS190124ac'),
    converts to a number, and checks if divisible by a number given in the
    configuration file.

    For example, if the configuration number 'joint_mdc_freq' is 10,
    this means joint events with superevents ending with 'j', 't', 'ad', etc.
    """
    end_string = re.split(r'\d+', graceid)[-1].lower()
    val = 0
    for i in range(len(end_string)):
        val += (ord(end_string[i]) - 96) * 26 ** (len(end_string) - i - 1)
    return val % int(app.conf['joint_mdc_freq']) == 0


@igwn_alert.handler('mdc_superevent',
                    shared=False)
def upload_external_event(alert):
    """Upload a random GRB event for a certain percentage of MDC superevents.

    Every n MDC superevents, upload a Fermi-like GRB candidate within the
    standard CBC-GRB search window, where the frequency n is determined by
    the configuration variable 'joint_mdc_freq'.
    """

    # Only create external MDC for the occasional MDC superevent
    if not _is_joint_mdc(alert['uid']) or alert['alert_type'] != 'new':
        return
    # Potentially upload 1, 2, or 3 GRB events
    num = 1 + np.random.choice(np.arange(3), p=[.6, .3, .1])
    events = []
    pipelines = []
    for i in range(num):
        gpstime = float(alert['object']['t_0'])
        new_time = _offset_time(gpstime)

        # Choose external grb pipeline to simulate
        pipeline = np.random.choice(['Fermi', 'Swift', 'INTEGRAL', 'AGILE'],
                                    p=[.5, .3, .1, .1])
        ext_event = create_grb_event(new_time, pipeline)

        # Upload as from GCN
        external_triggers.handle_grb_gcn(ext_event)

        events.append(ext_event), pipelines.append(pipeline)

    return events, pipelines
