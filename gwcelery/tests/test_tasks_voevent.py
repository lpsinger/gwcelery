import json
import socket
from threading import Thread
from time import sleep
from unittest.mock import MagicMock

from gcn.voeventclient import _recv_packet
import lxml.etree
import pkg_resources
import pytest

from ..tasks.voevent import handle, listen, send
from .. import app

# Test data
with pkg_resources.resource_stream(
        __name__, 'data/lvalert_voevent.json') as f:
    lvalert = json.load(f)
voevent = lvalert['object']['text']


@pytest.fixture
def send_thread():
    thread = Thread(target=send, args=(voevent,))
    thread.daemon = True
    thread.start()
    sleep(1)
    yield thread
    thread.join()
    if send.conn is not None:
        try:
            send.conn.close()
        except socket.error:
            pass
        send.conn = None


@pytest.mark.enable_socket
def test_send_connection_closed(send_thread):
    """Test sending a VOEvent over loopback to a connection that
    is immediately closed."""
    sock = socket.socket(socket.AF_INET)
    sock.connect(('127.0.0.1', 53410))
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()


@pytest.mark.enable_socket
def test_send(send_thread):
    """Test sending a VOEvent over loopback."""
    # First, simulate connecting from a disallowed IP address.
    # The connection should be refused.
    app.conf['gcn_remote_address'] = '192.0.2.0'
    sock = socket.socket(socket.AF_INET)
    try:
        sock.settimeout(0.1)
        with pytest.raises(socket.error):
            sock.connect(('127.0.0.1', 53410))
            packet = _recv_packet(sock)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        sock.close()

    # Now, simulate connecting from the allowed IP address.
    # The VOEvent should be received.
    app.conf['gcn_remote_address'] = '127.0.0.1'
    sock = socket.socket(socket.AF_INET)
    try:
        sock.settimeout(0.1)
        sock.connect(('127.0.0.1', 53410))
        packet = _recv_packet(sock)
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        sock.close()
    assert packet == voevent.encode('utf-8')


@pytest.fixture
def fake_gcn(celeryconf, monkeypatch):

    def mock_download(filename, graceid, service):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        assert service == 'https://gracedb.ligo.org/api/'
        return pkg_resources.resource_string(__name__, 'data/' + filename)

    def mock_get_log(graceid, service):
        assert graceid == 'G298048'
        assert service == 'https://gracedb.ligo.org/api/'
        return json.loads(
            pkg_resources.resource_string(__name__, 'data/G298048_log.json'))

    def mock_create_tag(tag, n, graceid, service):
        assert tag == 'gcn_received'
        assert n == 532
        assert graceid == 'G298048'
        assert service == 'https://gracedb.ligo.org/api/'

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


@pytest.mark.enable_socket
def test_listen(monkeypatch):
    """Test that the listen task would correctly launch gcn.listen()."""
    mock_gcn_listen = MagicMock()
    monkeypatch.setattr('gcn.listen', mock_gcn_listen)
    listen.run()
    mock_gcn_listen.assert_called_once_with(handler=handle)


def test_handle(fake_gcn):
    """Test that the fake GCN notice matches what we actually sent."""
    handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_mismatched_param(fake_gcn):
    """Test that we correctly detect mismatched parameter values in GCNs."""
    xpath = ".//Param[@name='SKYMAP_URL_FITS_BASIC']"
    fake_gcn.find(xpath).attrib['value'] = ('wrong, you fool!')
    with pytest.raises(
            AssertionError,
            match="^GCN parameter 'SKYMAP_URL_FITS_BASIC' has value 'wrong, "
            "you fool!', but original VOEvent parameter 'skymap_fits_basic' "
            "has value 'https://gracedb.ligo.org/apibasic/events/G298048/"
            "files/bayestar.fits.gz'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_unexpected_param(fake_gcn, monkeypatch):
    """Test that we correctly detect unexpected paremeters in GCNs."""

    def mock_download(filename, graceid, service):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        assert service == 'https://gracedb.ligo.org/api/'
        payload = pkg_resources.resource_string(__name__, 'data/' + filename)
        root = lxml.etree.fromstring(payload)
        elem = root.find(".//Group[@type='GW_SKYMAP']")
        elem.getparent().remove(elem)
        return lxml.etree.tostring(root)

    monkeypatch.setattr('gwcelery.tasks.gracedb.download', mock_download)

    with pytest.raises(
            AssertionError,
            match="^GCN has unexpected parameter: 'SKYMAP_URL_FITS_[A-Z]*'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_missing_param(fake_gcn, monkeypatch):
    """Test that we correctly detect unexpected paremeters in GCNs."""
    elem = fake_gcn.find(".//Param[@name='SKYMAP_URL_FITS_BASIC']")
    elem.getparent().remove(elem)
    with pytest.raises(
            AssertionError,
            match="^GCN is missing parameter: 'SKYMAP_URL_FITS_BASIC'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_wrong_ivorn_path(fake_gcn):
    """Test that we correctly detect the wrong IVORN path."""
    fake_gcn.attrib['ivorn'] = 'ivo://nasa.gsfc.gcn/wrong#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected path: '/wrong'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_wrong_ivorn_netloc(fake_gcn):
    """Test that we correctly detect the wrong IVORN netloc."""
    fake_gcn.attrib['ivorn'] = 'ivo://wrong/LVC#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected netloc: 'wrong'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)


def test_handle_wrong_ivorn_scheme(fake_gcn):
    """Test that we correctly detect the wrong IVORN scheme."""
    fake_gcn.attrib['ivorn'] = 'wrong://nasa.gsfc.gcn/LVC#G298048-1-Initial'
    with pytest.raises(
            AssertionError, match="^IVORN has unexpected scheme: 'wrong'$"):
        handle(lxml.etree.tostring(fake_gcn), fake_gcn)
