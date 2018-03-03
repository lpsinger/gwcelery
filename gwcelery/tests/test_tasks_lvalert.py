from __future__ import print_function
import os
import socket
from xml.etree.ElementTree import XML

from pyxmpp2.exceptions import DNSError

from ..tasks import lvalert
from . import *


def test_filter_messages():
    xml = XML(pkg_resources.resource_string(__name__, 'data/lvalert_xmpp.xml'))
    messages = list(lvalert.filter_messages(xml))
    assert len(messages) == 0


@pytest.fixture
def whitelist_cbc_gstlal_mdc():
    new_conf = dict(
        lvalert_node_whitelist={'cbc_gstlal_mdc'}
    )
    tmp = {key: app.conf[key] for key in new_conf.keys()}
    app.conf.update(new_conf)
    yield
    app.conf.update(tmp)


def test_filter_messages(whitelist_cbc_gstlal_mdc):
    xml = XML(pkg_resources.resource_string(__name__, 'data/lvalert_xmpp.xml'))
    messages = list(lvalert.filter_messages(xml))
    assert len(messages) == 1


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
def test_lvalert_constructor(netrc_lvalert):
    """Test that we at least attempt to connect to a non-existent URL."""
    with pytest.raises(DNSError):
        lvalert.listen()
