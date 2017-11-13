from __future__ import print_function
import os

from ..tasks import lvalert
from . import *


@pytest.fixture(autouse=True)
def tmpnetrc(tmpdir):
    path = str(tmpdir / 'netrc')
    with open(path, 'w') as f:
        print('machine', 'lvalert.invalid', file=f)
        print('login', 'albert.einstein', file=f)
        print('password', 'foobar', file=f)
    with patch.dict(os.environ, NETRC=path):
        yield


def test_lvalert_constructor():
    """We don't have a local test LVAlert server,
    so all we can test is the client initialization."""
    with pytest.raises(RuntimeError, message='No matching netrc entry found'):
        lvalert.LVAlertClient(None, 'lvalert2.invalid')
    lvalert.LVAlertClient(None, 'lvalert.invalid')
