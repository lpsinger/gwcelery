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

    xpath = ".//Param[@name='{}']"
    for orig_name, root_name in [
            ['skymap_fits_shib', 'SKYMAP_URL_FITS_SHIB'],
            ['skymap_fits_x509', 'SKYMAP_URL_FITS_X509'],
            ['skymap_fits_basic', 'SKYMAP_URL_FITS_BASIC'],
            ['skymap_png_shib', 'SKYMAP_URL_PNG_SHIB'],
            ['skymap_png_x509', 'SKYMAP_URL_PNG_X509'],
            ['skymap_png_basic', 'SKYMAP_URL_PNG_BASIC']]:

        orig_elem = orig.find(xpath.format(orig_name))
        root_elem = root.find(xpath.format(root_name))

        if orig_elem is None:
            assert root_elem is None, (
                'GCN has unexpected parameter: {!r}'.format(root_name))
        else:
            assert root_elem is not None, (
                'GCN is missing parameter: {!r}'.format(root_name))
            orig_value = orig_elem.attrib.get('value')
            root_value = root_elem.attrib.get('value')
            assert root_value == orig_value, (
                'GCN parameter {!r} has value {!r}, but '
                'original VOEvent parameter {!r} '
                'has value {!r}'.format(
                    root_name, root_value, orig_name, orig_value))

    # Find matching GraceDB log entry
    log = gracedb.get_log(graceid)
    entry, = (e for e in log if e['filename'] == filename)
    log_number = entry['N']

    # Tag the VOEvent to indicate that it was received correctly
    gracedb.create_tag('gcn_received', log_number, graceid)
