"""Create mock events from the "First Two Years" paper."""
import io

from celery.task import PeriodicTask
from celery.utils.log import get_task_logger
from glue.ligolw import utils
from glue.ligolw import lsctables
from glue.ligolw.table import get_table
import lal
from ligo.skymap.io.events.ligolw import ContentHandler
import numpy as np
import pkg_resources

from ..celery import app
from . import gracedb

log = get_task_logger(__name__)


@app.task(shared=False)
def pick_coinc():
    """Pick a coincidence from the "First Two Years" paper."""
    filename = pkg_resources.resource_filename(
        __name__, '../data/first2years/2016/gstlal.xml.gz')
    xmldoc = utils.load_filename(filename, contenthandler=ContentHandler)
    root, = xmldoc.childNodes

    # Remove unneeded tables
    for lsctable in (
            lsctables.FilterTable,
            lsctables.SegmentTable,
            lsctables.SegmentDefTable,
            lsctables.SimInspiralTable,
            lsctables.SummValueTable,
            lsctables.SearchSummVarsTable):
        root.removeChild(get_table(xmldoc, lsctable.tableName))

    coinc_inspiral_table = table = get_table(
        xmldoc, lsctables.CoincInspiralTable.tableName)

    # Determine event with most recent sideral time
    gps_time_now = lal.GPSTimeNow()
    gmsts = np.asarray([lal.GreenwichMeanSiderealTime(_.end) for _ in table])
    gmst_now = lal.GreenwichMeanSiderealTime(gps_time_now)
    div, rem = divmod(gmst_now - gmsts, 2 * np.pi)
    i = np.argmin(rem)
    new_gmst = div[i] * 2 * np.pi + gmsts[i]
    old_time = table[i].end
    new_time = lal.LIGOTimeGPS()
    result = lal.GreenwichMeanSiderealTimeToGPS(new_gmst, new_time)
    result.disown()
    del result
    delta_t = new_time - old_time
    target_coinc_event_id = int(table[i].coinc_event_id)

    # Remove unneeded rows
    table[:] = [row for row in table
                if int(row.coinc_event_id) == target_coinc_event_id]
    target_end_time = table[0].get_end()

    table = get_table(xmldoc, lsctables.CoincTable.tableName)
    table[:] = [row for row in table
                if int(row.coinc_event_id) == target_coinc_event_id]

    table = get_table(xmldoc, lsctables.CoincMapTable.tableName)
    table[:] = [row for row in table
                if int(row.coinc_event_id) == target_coinc_event_id]
    target_sngl_inspirals = frozenset(row.event_id for row in table)

    sngl_inspiral_table = table = get_table(
        xmldoc, lsctables.SnglInspiralTable.tableName)
    table[:] = [row for row in table if row.event_id in target_sngl_inspirals]

    table = get_table(xmldoc, lsctables.ProcessTable.tableName)
    table[:] = [row for row in table if row.program == 'gstlal_inspiral']
    target_process_ids = frozenset(row.process_id for row in table)

    table = get_table(xmldoc, lsctables.SearchSummaryTable.tableName)
    table[:] = [row for row in table if target_end_time in row.get_out()
                and row.process_id in target_process_ids]
    target_process_ids = frozenset(row.process_id for row in table)

    table = get_table(xmldoc, lsctables.ProcessTable.tableName)
    table[:] = [row for row in table if row.process_id in target_process_ids]

    table = get_table(xmldoc, lsctables.ProcessParamsTable.tableName)
    table[:] = [row for row in table if row.process_id in target_process_ids]

    # Shift event times
    for row in coinc_inspiral_table:
        row.end += delta_t
    for row in sngl_inspiral_table:
        row.end += delta_t
        row.end_time_gmst = lal.GreenwichMeanSiderealTime(row.end)

    coinc_xml = io.BytesIO()
    utils.write_fileobj(xmldoc, coinc_xml)
    return coinc_xml.getvalue()


@app.task(base=PeriodicTask, shared=False, run_every=720)
def upload_event():
    """Upload a random event from the "First Two Years" paper."""
    coinc = pick_coinc()
    psd = pkg_resources.resource_filename(
        __name__, '../data/first2years/2016/psd.xml.gz')
    with open(psd, 'rb') as f:
        psd = f.read()
    graceid = gracedb.create_event(coinc, 'MDC', 'gstlal', 'CBC')
    log.info('uploaded as %s', graceid)
    gracedb.upload(psd, 'psd.xml.gz', graceid, 'Noise PSD', ['psd'])
