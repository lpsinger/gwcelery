import json

import lxml.etree
import pkg_resources
import pytest

from ..tasks.gcn.validate import validate_voevent

# Test data
with pkg_resources.resource_stream(
        __name__, 'data/lvalert_voevent.json') as f:
    lvalert = json.load(f)
voevent = lvalert['object']['text']


@pytest.fixture
def fake_gcn(celeryconf, monkeypatch):

    def mock_download(filename, graceid):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        return pkg_resources.resource_string(__name__, 'data/' + filename)

    def mock_get_log(graceid):
        assert graceid == 'G298048'
        return json.loads(
            pkg_resources.resource_string(__name__, 'data/G298048_log.json'))

    def mock_create_tag(tag, n, graceid):
        assert tag == 'gcn_received'
        assert n == 532
        assert graceid == 'G298048'

    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.download', mock_download)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.get_log', mock_get_log)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.create_tag', mock_create_tag)

    # Check the real GCN notice, which is valid.
    payload = pkg_resources.resource_string(
        __name__, 'data/G298048-1-Initial.gcn.xml')
    root = lxml.etree.fromstring(payload)
    yield root


def test_validate_voevent(fake_gcn):
    """Test that the fake GCN notice matches what we actually sent."""
    validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_mismatched_param(fake_gcn):
    """Test that we correctly detect mismatched parameter values in GCNs."""
    xpath = ".//Param[@name='SKYMAP_URL_FITS_BASIC']"
    fake_gcn.find(xpath).attrib['value'] = ('wrong, you fool!')
    with pytest.raises(
            AssertionError,
            match="^GCN parameter 'SKYMAP_URL_FITS_BASIC' has value 'wrong, "
            "you fool!', but original VOEvent parameter 'skymap_fits_basic' "
            "has value 'https://gracedb.ligo.org/apibasic/events/G298048/"
            "files/bayestar.fits.gz'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_unexpected_param(fake_gcn, monkeypatch):
    """Test that we correctly detect unexpected paremeters in GCNs."""

    def mock_download(filename, graceid):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        payload = pkg_resources.resource_string(__name__, 'data/' + filename)
        root = lxml.etree.fromstring(payload)
        elem = root.find(".//Group[@type='GW_SKYMAP']")
        elem.getparent().remove(elem)
        return lxml.etree.tostring(root)

    monkeypatch.setattr('gwcelery.tasks.gracedb.download', mock_download)

    with pytest.raises(
            AssertionError,
            match="^GCN has unexpected parameter: 'SKYMAP_URL_FITS_[A-Z]*'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_missing_param(fake_gcn, monkeypatch):
    """Test that we correctly detect unexpected paremeters in GCNs."""
    elem = fake_gcn.find(".//Param[@name='SKYMAP_URL_FITS_BASIC']")
    elem.getparent().remove(elem)
    with pytest.raises(
            AssertionError,
            match="^GCN is missing parameter: 'SKYMAP_URL_FITS_BASIC'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_wrong_ivorn_path(fake_gcn):
    """Test that we correctly detect the wrong IVORN path."""
    fake_gcn.attrib['ivorn'] = 'ivo://nasa.gsfc.gcn/wrong#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected path: '/wrong'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_wrong_ivorn_netloc(fake_gcn):
    """Test that we correctly detect the wrong IVORN netloc."""
    fake_gcn.attrib['ivorn'] = 'ivo://wrong/LVC#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected netloc: 'wrong'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))


def test_validate_voevent_wrong_ivorn_scheme(fake_gcn):
    """Test that we correctly detect the wrong IVORN scheme."""
    fake_gcn.attrib['ivorn'] = 'wrong://nasa.gsfc.gcn/LVC#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected scheme: 'wrong'$"):
        validate_voevent(lxml.etree.tostring(fake_gcn))
