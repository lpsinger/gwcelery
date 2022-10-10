"""Create mock events from the "First Two Years" paper."""
from importlib import resources
import io
import random

from celery import group
from celery.utils.log import get_task_logger
from ligo.lw.table import Table
from ligo.lw import utils
from ligo.lw import lsctables
import lal
from ligo.skymap.io.events.ligolw import ContentHandler
import numpy as np

from .core import get_last
from ..data import first2years as data_first2years
from ..import app
from . import gracedb

log = get_task_logger(__name__)


def pick_coinc():
    """Pick a coincidence from the "First Two Years" paper."""
    with resources.open_binary(data_first2years, 'gstlal.xml.gz') as f:
        xmldoc = utils.load_fileobj(f, contenthandler=ContentHandler)
    root, = xmldoc.childNodes

    # Remove unneeded tables
    for name in (
            'filter',  # lsctables.FilterTable removed from ligo.lw
            lsctables.SegmentTable.tableName,
            lsctables.SegmentDefTable.tableName,
            lsctables.SimInspiralTable.tableName,
            lsctables.SummValueTable.tableName,
            lsctables.SearchSummVarsTable.tableName):
        root.removeChild(Table.get_table(xmldoc, name))

    coinc_inspiral_table = table = lsctables.CoincInspiralTable.get_table(
        xmldoc)

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
    target_end_time = table[0].end

    coinc_table = table = lsctables.CoincTable.get_table(xmldoc)
    table[:] = [row for row in table
                if int(row.coinc_event_id) == target_coinc_event_id]

    table = lsctables.CoincMapTable.get_table(xmldoc)
    table[:] = [row for row in table
                if int(row.coinc_event_id) == target_coinc_event_id]
    target_sngl_inspirals = frozenset(row.event_id for row in table)

    sngl_inspiral_table = table = lsctables.SnglInspiralTable.get_table(xmldoc)
    table[:] = [row for row in table if row.event_id in target_sngl_inspirals]

    table = lsctables.ProcessTable.get_table(xmldoc)
    table[:] = [row for row in table if row.program == 'gstlal_inspiral']
    target_process_ids = frozenset(row.process_id for row in table)

    table = lsctables.SearchSummaryTable.get_table(xmldoc)
    table[:] = [row for row in table if target_end_time in row.out_segment
                and row.process_id in target_process_ids]
    target_process_ids = frozenset(row.process_id for row in table)

    table = lsctables.ProcessTable.get_table(xmldoc)
    table[:] = [row for row in table if row.process_id in target_process_ids]

    table = lsctables.ProcessParamsTable.get_table(xmldoc)
    table[:] = [row for row in table if row.process_id in target_process_ids]

    # Shift event times
    for row in coinc_inspiral_table:
        row.end += delta_t
    for row in sngl_inspiral_table:
        row.end += delta_t
        row.end_time_gmst = lal.GreenwichMeanSiderealTime(row.end)

    # The old version of gstlal used to produce the "First Two Years" data set
    # stored likelihood in the coinc_event.likelihood column, but newer
    # versions store the *natural log* of the likelihood here. The p_astro
    # calculation requires this to be log likelihood.
    for row in coinc_table:
        row.likelihood = np.log(row.likelihood)

    # Gstlal stores the template's SVD bank index in the Gamma1 column.
    # Fill this in so that we can calculate p_astro
    # (see :mod:`gwcelery.tasks.p_astro_gstlal`).
    for row in sngl_inspiral_table:
        row.Gamma1 = 16

    coinc_xml = io.BytesIO()
    utils.write_fileobj(xmldoc, coinc_xml)
    return coinc_xml.getvalue()


def _jitter_snr(coinc_bytes):
    coinc_xml = io.BytesIO(coinc_bytes)
    xmldoc = utils.load_fileobj(coinc_xml, contenthandler=ContentHandler)

    coinc_inspiral_table = lsctables.CoincInspiralTable.get_table(xmldoc)

    # Add a tiny amount of jitter in SNR so that uploads have random
    # preferred event precedence.
    for row in coinc_inspiral_table:
        row.snr += random.gauss(0, 1e-9)

    coinc_xml = io.BytesIO()
    utils.write_fileobj(xmldoc, coinc_xml)
    return coinc_xml.getvalue()


@app.task(shared=False)
def _vet_event(superevents):
    if superevents:
        gracedb.create_signoff.s(
            random.choice(['NO', 'OK']),
            'If this had been a real gravitational-wave event candidate, '
            'then an on-duty scientist would have left a comment here on '
            'data quality and the status of the detectors.',
            'ADV', superevents[0]['superevent_id']
        ).apply_async()


@app.task(shared=False)
def _log_event_and_return_query(event):
    graceid = event['graceid']
    log.info('uploaded as %s', graceid)
    return 'MDC event: {}'.format(graceid)


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    """Register periodic tasks.

    See
    https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html.
    """
    sender.add_periodic_task(3600.0, upload_event)


@app.task(ignore_result=True, shared=False)
def upload_event():
    """Upload a random event from the "First Two Years" paper.

    After 2 minutes, randomly either retract or confirm the event to send a
    retraction or initial notice respectively.
    """
    coinc = pick_coinc()
    num = 16 if app.conf['mock_events_simulate_multiple_uploads'] else 1

    (
        group(
            gracedb.create_event.si(
                 _jitter_snr(coinc), 'MDC', 'gstlal', 'CBC'
            ) for _ in range(num)
        )
        |
        get_last.s()
        |
        _log_event_and_return_query.s()
        |
        gracedb.get_superevents.s().set(countdown=600)
        |
        _vet_event.s()
    ).apply_async()
