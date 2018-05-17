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


@patch('gwcelery.tasks.orchestrator.dispatch.run')
def test_handle_messages(mock_dispatch, netrc_lvalert):
    xml = XML(pkg_resources.resource_string(__name__, 'data/lvalert_xmpp.xml'))
    json = xml.find('.//ns2:entry', lvalert.ns).text
    lvalert._handle_messages(xml)
    mock_dispatch.assert_called_once_with(json)
