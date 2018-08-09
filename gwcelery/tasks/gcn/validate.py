"""Validate LIGO/Virgo GCN notices to make sure that their contents match the
original VOEvent notices that we sent."""
from urllib.parse import urlparse

import lxml.etree
from pytest import approx

from .. import gcn
from .. import gracedb


PARAM_TYPES = {'int': int,
               'float': float,
               'string': str}

NAME_MAPPING = (('skymap_fits_shib', 'SKYMAP_URL_FITS_SHIB'),
                ('skymap_fits_x509', 'SKYMAP_URL_FITS_X509'),
                ('skymap_fits_basic', 'SKYMAP_URL_FITS_BASIC'),
                ('skymap_png_shib', 'SKYMAP_URL_PNG_SHIB'),
                ('skymap_png_x509', 'SKYMAP_URL_PNG_X509'),
                ('skymap_png_basic', 'SKYMAP_URL_PNG_BASIC'),
                ('FAR', 'FAR'),
                ('EventPage', 'EventPage'),
                ('AlertType', 'AlertType'),
                ('GraceID', 'GraceID'),
                ('Group', 'Group'),
                ('Search', 'Search'),
                ('Pipeline', 'Pipeline'),
                ('ProbHasNS', 'ProbHasNS'),
                ('ProbHasRemnant', 'ProbHasRemnant'),
                ('internal', 'Internal'),
                ('Retraction', 'Retraction'),
                ('HardwareInj', 'HardwareInj'),
                ('Vetted', 'Vetted'),
                ('OpenAlert', 'OpenAlert'))

FLAGS = {'internal', 'Retraction', 'HardwareInj', 'Vetted', 'OpenAlert'}

DETECTOR_MAPPING = (('H1', 'LHO'),
                    ('L1', 'LLO'),
                    ('V1', 'Virgo'),
                    ('G1', 'GEO600'),
                    ('K1', 'KAGRA'),
                    ('I1', 'LIO'))


def _to_bool(s):
    if s in {'true', '1', 1}:
        return True
    elif s in {'false', '0', 0}:
        return False
    else:
        raise ValueError('Could not convert {!r} to bool'.format(s))


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

    # Which VOEvent does this refer to?
    u = urlparse(root.attrib['ivorn'])
    assert u.scheme == 'ivo', (
        'IVORN has unexpected scheme: {!r}'.format(u.scheme))
    assert u.netloc == 'nasa.gsfc.gcn', (
        'IVORN has unexpected netloc: {!r}'.format(u.netloc))
    assert u.path == '/LVC', (
        'IVORN has unexpected path: {!r}'.format(u.path))
    local_id = u.fragment
    filename = local_id + '.xml'

    # Download and parse original VOEvent
    orig = lxml.etree.fromstring(gracedb.download(filename, graceid))

    # Does the event time match?
    xpath = ('./WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords'
             '/Time/TimeInstant/ISOTime')
    orig_time = orig.find(xpath).text
    root_time = root.find(xpath).text
    assert root_time == orig_time, (
        'GCN VOEvent has event time {!r}, '
        'but original VOEvent has event time {!r}'.format(
            root_time, orig_time))

    # Do parameters match?
    xpath = ".//Param[@name='{}']"
    for orig_name, root_name in NAME_MAPPING:

        orig_elem = orig.find(xpath.format(orig_name))
        root_elem = root.find(xpath.format(root_name))

        if orig_elem is None:
            assert root_elem is None, (
                'GCN has unexpected parameter: {!r}'.format(root_name))
        else:
            assert root_elem is not None, (
                'GCN is missing parameter: {!r}'.format(root_name))

            if orig_name in FLAGS:
                tp = _to_bool
            else:
                orig_type = orig_elem.attrib.get('dataType', 'string')
                root_type = root_elem.attrib.get('dataType', 'string')
                assert orig_type == root_type, (
                    'GCN parameter {!r} has type {!r}, but '
                    'original VOEvent parameter {!r} '
                    'has type {!r}'.format(
                        root_name, root_type, orig_name, orig_type))
                tp = PARAM_TYPES.get(orig_type, str)

            orig_value = tp(orig_elem.attrib.get('value'))
            root_value = tp(root_elem.attrib.get('value'))

            if tp is float:
                orig_value = approx(orig_value, rel=1e-3)

            # Some special cases where GCN uses a different string from us...
            if root_name == 'Search' and root_value == 'MockDataChallenge':
                root_value = 'MDC'
            elif root_name == 'Pipeline' and root_value == 'GSTLAL':
                root_value = 'gstlal'

            assert root_value == orig_value, (
                'GCN parameter {!r} has value {!r}, but '
                'original VOEvent parameter {!r} '
                'has value {!r}'.format(
                    root_name, root_value, orig_name, orig_value))

    # Do the detectors that were on match?
    orig_prefixes = {s.partition(':')[0]
                     for s in orig.xpath('./How/Description/text()')}
    for orig_prefix, root_prefix in DETECTOR_MAPPING:
        sel = xpath.format(root_prefix + '_participated')
        orig_on = (orig_prefix in orig_prefixes)
        root_on = _to_bool(root.find(sel).attrib['value'])
        assert orig_on == root_on, (
            'GCN VOEvent claims that detector {} state is {!r}, but original '
            'VOEvent states that state is {!r}'.format(
                orig_prefix, root_on, orig_on))

    # Find matching GraceDB log entry
    log = gracedb.get_log(graceid)
    entry, = (e for e in log if e['filename'] == filename)
    log_number = entry['N']

    # Tag the VOEvent to indicate that it was received correctly
    gracedb.create_tag('gcn_received', log_number, graceid)
