from __future__ import print_function
import os

from pyxmpp2.exceptions import DNSError

from ..tasks import lvalert
from . import *


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
        lvalert.lvalert_listen()


@pytest.fixture
def netrc_lvalert(tmpdir):
    path = str(tmpdir / 'netrc')
    with open(path, 'w') as f:
        print('machine', 'lvalert.invalid', file=f)
        print('login', 'albert.einstein', file=f)
        print('password', 'foobar', file=f)
    with patch.dict(os.environ, NETRC=path):
        yield


def test_lvalert_constructor(netrc_lvalert):
    """Test that we at least attempt to connect to a non-existent URL."""
    with pytest.raises(DNSError):
        lvalert.lvalert_listen()
