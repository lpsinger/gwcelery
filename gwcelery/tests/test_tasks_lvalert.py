import json
import logging
import os
import socket
from unittest.mock import patch
from xml.etree.ElementTree import XML

import pkg_resources
from pyxmpp2.exceptions import DNSError
import pytest

from ..tasks import lvalert


@pytest.fixture
def netrc_lvalert2(tmpdir):
    path = str(tmpdir / 'netrc')
    with open(path, 'w') as f:
        print('machine', 'lvalert2.invalid', file=f)
        print('login', 'albert.einstein', file=f)
        print('password', 'foobar', file=f)
    with patch.dict(os.environ, NETRC=path):
        yield


def test_lvalert_netrc_does_not_match(netrc_lvalert2):
    """Test that we get the correct error message when the lvalert host is
    not in the netrc file."""
    with pytest.raises(RuntimeError, match='No matching netrc entry found'):
        lvalert.listen()


@pytest.fixture
def netrc_lvalert(tmpdir):
    path = str(tmpdir / 'netrc')
    with open(path, 'w') as f:
        print('machine', 'lvalert.invalid', file=f)
        print('login', 'albert.einstein', file=f)
        print('password', 'foobar', file=f)
    with patch.dict(os.environ, NETRC=path):
        yield


try:
    socket.gethostbyname('lvalert.invalid')
except socket.error:
    resolves_invalid_urls = False
else:
    resolves_invalid_urls = True


@pytest.mark.skipif(
    resolves_invalid_urls, reason='your DNS server is resolving invalid '
    'hostnames (maybe a home internet provider that provides a default '
    'landing page?)')
@pytest.mark.enable_socket
def test_lvalert_constructor(netrc_lvalert):
    """Test that we at least attempt to connect to a non-existent URL."""
    with pytest.raises(DNSError):
        lvalert.listen()


@pytest.fixture
def fake_lvalert():
    xml = XML(pkg_resources.resource_string(__name__, 'data/lvalert_xmpp.xml'))
    entry = xml.find('.//ns2:entry', lvalert.ns)
    return xml, entry


@pytest.mark.skip(reason="Raising AttributeError with current gracedb-client")
@patch('gwcelery.tasks.orchestrator.dispatch.run')
def test_handle_messages(mock_dispatch, netrc_lvalert, fake_lvalert):
    """Test handling an LVAlert message that originates from the configured
    GraceDb server."""
    xml, entry = fake_lvalert

    # Manipulate alert content
    alert = json.loads(entry.text)
    alert['object']['self'] = \
        alert['object']['self'].replace('gracedb.ligo.org', 'gracedb.invalid')
    entry.text = json.dumps(alert)

    # Run function under test
    lvalert._handle_messages(xml)
    mock_dispatch.assert_called_once_with(entry.text)


@patch('gwcelery.tasks.orchestrator.dispatch.run')
def test_handle_messages_wrong_server(mock_dispatch, netrc_lvalert,
                                      fake_lvalert, caplog):
    """Test handling an LVAlert message that originates from a GraceDb server
    other than the configured GraceDb server. It should be ignored."""
    xml, entry = fake_lvalert

    # Manipulate alert content
    alert = json.loads(entry.text)
    alert['object']['self'] = \
        alert['object']['self'].replace('gracedb.ligo.org', 'gracedb2.invalid')
    entry.text = json.dumps(alert)

    # Run function under test
    lvalert._handle_messages(xml)

    # Run function under test
    caplog.set_level(logging.WARNING)
    lvalert._handle_messages(xml)
    record, *_ = caplog.records
    assert record.message == ('ignoring LVAlert message because it is '
                              'intended for GraceDb server '
                              'https://gracedb2.invalid/api/, but we are set '
                              'up for server https://gracedb.invalid/api/')
    mock_dispatch.assert_not_called()


@patch('gwcelery.tasks.orchestrator.dispatch.run')
def test_handle_messages_no_self_link(mock_dispatch, netrc_lvalert,
                                      fake_lvalert, caplog):
    """Test handling an LVAlert message that does not identify the GraceDb
    server of origin. It should be rejected."""
    xml, entry = fake_lvalert

    # Manipulate alert content
    alert = json.loads(entry.text)
    del alert['object']['self']
    entry.text = json.dumps(alert)

    # Run function under test
    caplog.set_level(logging.ERROR)
    lvalert._handle_messages(xml)
    record, = caplog.records
    assert 'LVAlert message does not contain an API URL' in record.message
    mock_dispatch.assert_not_called()
