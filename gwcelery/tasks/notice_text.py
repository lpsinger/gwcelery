"""Tasks to validate the GCN Notice types of the e-mail formats [GCN e-mail]_.

References
----------
.. [GCN e-mail] https://gcn.gsfc.nasa.gov/lvc.html#tc13

"""
import email
import email.policy
from math import isclose

from celery.utils.log import get_task_logger
import lxml.etree

from .. import app
from ..email.signals import email_received
from . import gracedb

log = get_task_logger(__name__)


def _trigger_datetime(gcn_notice_mail):
    """Get trigger data and time from a GCN email notice."""
    trigger_date = gcn_notice_mail[
        "TRIGGER_DATE"].split()[4].replace("/", "-")

    trigger_time = gcn_notice_mail[
        "TRIGGER_TIME"].split()[2].replace("{", "").replace("}", "")

    trigger_datetime = (f'{trigger_date}T{trigger_time}')

    return trigger_datetime


def _vo_match_notice(gcn_notice_mail, params_vo, trigger_time_vo):
    """Match the notice-email and the VOtable keywords."""
    dict_checks = {}

    # TRIGGER_DATE+TRIGGER_TIME
    trigger_datetime_notice_mail = _trigger_datetime(gcn_notice_mail)

    match_trigger_datetime = (
        trigger_datetime_notice_mail == trigger_time_vo)
    dict_checks['TRIGGER_DATETIME'] = match_trigger_datetime

    # SEQUENCE_NUM
    match_sequence_num = (
        gcn_notice_mail["SEQUENCE_NUM"].split()[0] == params_vo["Pkt_Ser_Num"])
    dict_checks['SEQUENCE_NUM'] = match_sequence_num

    if params_vo['AlertType'] == 'Retraction':
        return dict_checks

    # Notice keywords
    notice_keys = ({"types": ["GROUP_TYPE", "PIPELINE_TYPE", "SEARCH_TYPE"],
                    "classif_props_cbc": ["PROB_NS", "PROB_REMNANT",
                                          "PROB_BNS", "PROB_NSBH", "PROB_BBH",
                                          "PROB_TERRES"],
                    "urls": ["SKYMAP_FITS_URL", "EVENTPAGE_URL"],
                    "classif_props_burst": ["CENTRAL_FREQ", "DURATION"]})

    # Votable keywords
    vo_keys = ({"types": ["Group", "Pipeline", "Search"],
                "classif_props_cbc": ["HasNS", "HasRemnant", "BNS",
                                      "NSBH", "BBH", "Terrestrial"],
                "urls": ["skymap_fits", "EventPage"],
                "classif_props_burst": ["CentralFreq", "Duration"]})

    # FAR
    far_notice = float(gcn_notice_mail["FAR"].split()[0])
    match_far = isclose(far_notice, float(params_vo["FAR"]), rel_tol=0.001)
    dict_checks['FAR'] = match_far

    # Group and pipeline types
    for notice_key, vo_key in zip(notice_keys["types"], vo_keys["types"]):
        value_notice = gcn_notice_mail[notice_key].split()[2]
        match = (value_notice == params_vo[vo_key])
        dict_checks[notice_key] = match

    # EventPage/EVENTPAGE_URL and skymap_fits/SKYMAP_FITS_URL
    for notice_key, vo_key in zip(notice_keys["urls"], vo_keys["urls"]):
        value_notice = gcn_notice_mail[notice_key]
        match = (value_notice == params_vo[vo_key])
        dict_checks[notice_key] = match

    # CBC classification and properties
    if params_vo['Group'] == 'CBC':
        for notice_key, vo_key, in zip(notice_keys["classif_props_cbc"],
                                       vo_keys["classif_props_cbc"]):
            value_notice = float(gcn_notice_mail[notice_key].split()[0])
            match = isclose(value_notice, float(params_vo[vo_key]),
                            abs_tol=0.01)
            dict_checks[notice_key] = match

    # Burst Properties
    if params_vo['Group'] == 'Burst':
        for notice_key, vo_key in zip(notice_keys["classif_props_burst"],
                                      vo_keys["classif_props_burst"]):
            value_notice = float(gcn_notice_mail[notice_key].split()[0])
            match = isclose(value_notice,
                            float(params_vo[vo_key]), rel_tol=0.001)
            dict_checks[notice_key] = match

    return dict_checks


def _vo_match_comments(gcn_notice_mail, params_vo):
    """Check the notice-email comments for the contributed instruments."""
    dict_check_comments = {}

    comments_notice_mail = gcn_notice_mail.get_all("COMMENTS")
    instruments_vo = params_vo["Instruments"]

    text = ' contributed to this candidate event.'
    gcn_to_vo_instruments = {'LIGO-Hanford Observatory': 'H1',
                             'LIGO-Livingston Observatory': 'L1',
                             'VIRGO Observatory': 'V1'}

    instrument_comments = (line.strip() for line in comments_notice_mail)
    instruments_gcn = {gcn_to_vo_instruments[line[:-len(text)]]
                       for line in instrument_comments if line.endswith(text)}

    instruments_vo = set(instruments_vo.split(','))
    match_instruments = (instruments_gcn == instruments_vo)
    dict_check_comments["INSTRUMENT"] = match_instruments

    return dict_check_comments


@email_received.connect
def on_email_received(rfc822, **kwargs):
    """Read the RFC822 email."""
    message = email.message_from_bytes(rfc822, policy=email.policy.default)
    validate_text_notice.s(message).delay()


@app.task(shared=False)
def validate_text_notice(message):
    """Validate LIGO/Virgo GCN e-mail notice format.

    Check that the contents of a public LIGO/Virgo GCN e-mail notice format
    matches the original VOEvent in GraceDB.

    """
    # Filter from address and subject
    if message['From'] != 'Bacodine <vxw@capella2.gsfc.nasa.gov>':
        log.info('Email is not from BACODINE. Subject:%s', message['Subject'])
        log.info('Sender is: %s', message['From'])
        return

    # Write message log
    log.info('Validating Notice: Subject:%s', message['Subject'])

    # Parse body email
    bodymsg = message.get_payload()
    notice = email.message_from_string(bodymsg)

    # Get notice type
    notice_type = notice['NOTICE_TYPE']

    if notice_type.split(" ")[-1] == "Skymap":
        notice_type = notice_type.split(" ")[-2]
    else:
        notice_type = notice_type.split(" ")[-1]

    # Get gracedb id and sequence number
    trigger_num = notice['TRIGGER_NUM']
    sequence_num = notice['SEQUENCE_NUM']

    # Download VOevent
    filename = f'{trigger_num}-{sequence_num}-{notice_type}.xml'
    payload = gracedb.download(filename, trigger_num)

    # Parse VOevent
    root = lxml.etree.fromstring(payload)

    params_vo = {elem.attrib['name']:
                 elem.attrib['value']
                 for elem in root.iterfind('.//Param')}

    trigger_time_vo = root.findtext('.//ISOTime')

    # Match
    filename_email = 'email_' + filename.replace('.xml', '.txt')
    gracedb.upload.delay(bodymsg, filename_email, trigger_num,
                         'email notice corresponding to ' + filename,
                         tags=['em_follow'])

    error = None
    try:
        if notice_type == 'Retraction':
            match = _vo_match_notice(notice, params_vo, trigger_time_vo)
        elif params_vo['Group'] in ["CBC", "Burst"]:
            match = {**_vo_match_notice(notice, params_vo, trigger_time_vo),
                     **_vo_match_comments(notice, params_vo)}
        else:
            match = []
            error = f'Email notice {filename} has unknown notice type'

        mismatched = ' '.join(key for key, value in match.items() if not value)
        if mismatched:
            error = \
                f'Email notice {filename} has mismatched keys: {mismatched}'
    except KeyError as err:
        # Since there was an exeception, the gcn was not annnotated
        error = f'Email notice {filename} missing key: {err}'

    if error:
        gracedb.create_tag.delay(filename, 'gcn_email_notok', trigger_num)
        gracedb.upload.delay(None, None, trigger_num,
                             error, tags=['em_follow'])
    else:
        gracedb.create_tag.delay(filename, 'gcn_email_ok', trigger_num)
